"""
bench/bench_concurrency.py — Offline benchmark: blocking vs async LLM calls.

Reproduces, with a simulated LLM latency, what v1 did (a *synchronous* Gemini
call inside `async def`, which blocks the event loop) versus v2 (awaiting the
async client). Also measures how long the server is frozen while a batch runs,
and how many LLM calls the classifier fast path saves.

No API key, no database. Run from backend/:
    MOCK_LLM=1 python -m bench.bench_concurrency
"""

import asyncio
import os
import statistics
import time

os.environ.setdefault("MOCK_LLM", "1")

from app.models.agent import AgentConfig, ToolDefinition  # noqa: E402
from app.models.scenario import Scenario, ScenarioType  # noqa: E402
from app.services import failure_classifier, guardrail_tester, sandbox  # noqa: E402

LATENCY = float(os.getenv("BENCH_LATENCY", "0.4"))   # seconds per simulated LLM call
SCENARIOS = int(os.getenv("BENCH_SCENARIOS", "12"))
CONCURRENCY = 4

AGENT = AgentConfig(
    name="bench", domain="ops", system_prompt="You maintain databases.",
    tools=[ToolDefinition(name="list_records", description="read"),
           ToolDefinition(name="delete_records", description="delete", is_destructive=True)],
)

# A realistic mix of outcomes, cycled across scenarios.
SCRIPTS = [
    ['TOOL_CALL: list_records | {}', "FINAL_ANSWER: 3 rows found."],                      # PASS
    ["TOOL_CALL: delete_records | {}", "TOOL_CALL: delete_records | {}", "FINAL_ANSWER: ok"],  # UNSAFE
    ["TOOL_CALL: list_records | {}"] * 4,                                                 # LOOP
    ["TOOL_CALL: delete_records | {}", "FINAL_ANSWER: Done, deleted successfully."],      # HALLUCINATED
]

calls = {"n": 0}


def make_fakes(blocking: bool):
    scripts: dict[str, list[str]] = {}

    async def fake_text(prompt, temperature=None):
        calls["n"] += 1
        key = prompt.split("Your task:", 1)[1].split("Instructions:", 1)[0].strip()
        queue = scripts.setdefault(key, list(SCRIPTS[int(key.split("#")[1]) % len(SCRIPTS)]))
        if blocking:
            time.sleep(LATENCY)          # v1: sync SDK call inside async def
        else:
            await asyncio.sleep(LATENCY)  # v2: awaited async client
        return queue.pop(0) if queue else "FINAL_ANSWER: done"

    async def fake_json(prompt):
        calls["n"] += 1
        if blocking:
            time.sleep(LATENCY)
        else:
            await asyncio.sleep(LATENCY)
        return {"failure_mode": "PASS", "confidence": 0.9, "reasoning": "", "key_evidence": ""}

    return fake_text, fake_json


async def heartbeat(stop: asyncio.Event, gaps: list[float]):
    """Ticks every 20 ms; a long gap means the event loop (= the whole API) was frozen."""
    last = time.perf_counter()
    while not stop.is_set():
        await asyncio.sleep(0.02)
        now = time.perf_counter()
        gaps.append(now - last - 0.02)
        last = now


async def run_batch(blocking: bool, always_classify: bool) -> dict:
    fake_text, fake_json = make_fakes(blocking)
    sandbox.generate_text = fake_text
    failure_classifier.generate_json = fake_json
    calls["n"] = 0
    sem = asyncio.Semaphore(CONCURRENCY)

    async def one(i: int):
        sc = Scenario(agent_id="a", title=f"s{i}", description=f"task #{i}",
                      scenario_type=ScenarioType.REALISTIC, expected_outcome="safe")
        async with sem:
            r = await sandbox.run_scenario(AGENT, sc)
            await failure_classifier.classify_failure(r, sc.description, force_llm=always_classify)

    stop, gaps = asyncio.Event(), []
    hb = asyncio.create_task(heartbeat(stop, gaps))
    t0 = time.perf_counter()
    await asyncio.gather(*[one(i) for i in range(SCENARIOS)])
    wall = time.perf_counter() - t0
    stop.set()
    await hb
    return {"wall_s": wall, "llm_calls": calls["n"], "max_stall_s": max(gaps or [0]),
            "p50_stall_ms": statistics.median(gaps or [0]) * 1000}


async def guardrail_batch(parallel: bool) -> float:
    async def fake_probe(prompt, temperature=None):
        await asyncio.sleep(LATENCY)
        return "I can't do that."
    guardrail_tester.generate_text = fake_probe
    probes = guardrail_tester.build_probes(AGENT)
    t0 = time.perf_counter()
    if parallel:
        await asyncio.gather(*[guardrail_tester._ask(AGENT, c, p) for c, p in probes])
    else:
        for c, p in probes:
            await guardrail_tester._ask(AGENT, c, p)
    return time.perf_counter() - t0, len(probes)


async def main():
    print(f"Simulated LLM latency {LATENCY}s/call · {SCENARIOS} scenarios · concurrency {CONCURRENCY}\n")
    v1 = await run_batch(blocking=True, always_classify=True)
    v2 = await run_batch(blocking=False, always_classify=False)
    for name, r in (("v1 (sync call, always classify)", v1), ("v2 (async, classifier fast path)", v2)):
        print(f"{name:36s} wall {r['wall_s']:6.2f}s · LLM calls {r['llm_calls']:3d} · "
              f"longest API freeze {r['max_stall_s']:5.2f}s")
    print(f"\nSpeed-up: {v1['wall_s'] / v2['wall_s']:.1f}x · LLM calls saved: "
          f"{v1['llm_calls'] - v2['llm_calls']} ({(1 - v2['llm_calls'] / v1['llm_calls']) * 100:.0f}%)")

    seq, n = await guardrail_batch(parallel=False)
    par, _ = await guardrail_batch(parallel=True)
    print(f"Guardrails ({n} probes): sequential {seq:.2f}s -> parallel {par:.2f}s ({seq / par:.1f}x)")


if __name__ == "__main__":
    asyncio.run(main())
