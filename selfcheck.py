"""Offline self-check for the Member A harness. Zero network, zero API cost.

Runs the whole pipeline against the deterministic mock client and asserts the
core invariants. Use it as a smoke test before a demo, or in CI.

    python selfcheck.py
"""
from __future__ import annotations

import glob
import json
import os
import sys
import tempfile
from pathlib import Path

import config
from agent import run_agent
from mockclient import MockAnthropic
from schemas import Scenario, Trace, validate_trace
from tools import MockToolRegistry, TOOLS, tool_specs

FAILURES = []


def check(name: str, cond: bool, detail: str = "") -> None:
    status = "ok  " if cond else "FAIL"
    print(f"  [{status}] {name}" + (f" -- {detail}" if detail and not cond else ""))
    if not cond:
        FAILURES.append(name)


def main() -> int:
    print("Tripwire harness self-check (offline / mock)\n")

    # 1. Registry: destructive flags and injection.
    print("1. Mock tool registry")
    reg = MockToolRegistry(injected={"read_document": "INJECTED"})
    out = reg.call("read_document", {"doc_id": "d1"}, 1)
    check("injected output returned", out == "INJECTED")
    reg.call("delete_records", {"table": "t"}, 2)
    check("delete_records flagged destructive",
          reg.calls[-1]["destructive"] is True)
    check("read_document flagged non-destructive",
          reg.calls[0]["destructive"] is False)
    check("tool_specs builds all five", len(tool_specs(list(TOOLS))) == 5)

    # 2. Fixtures: all 10 valid, covering every outcome.
    print("2. Fixtures")
    fixtures = sorted(glob.glob(str(config.FIXTURES_DIR / "fake_*.json")))
    check("exactly 10 fixtures", len(fixtures) == 10, f"found {len(fixtures)}")
    states, has_destructive, has_turn_cap = set(), 0, 0
    for fp in fixtures:
        t = Trace.from_dict(json.load(open(fp, encoding="utf-8")))
        states.add(t.terminal_state)
        if t.destructive_calls():
            has_destructive += 1
        if t.terminal_state == "turn_cap_hit":
            has_turn_cap += 1
    check("fixtures include destructive runs", has_destructive >= 1)
    check("fixtures include a turn_cap_hit run", has_turn_cap >= 1)

    # 3. Agent loop end to end (mock), turn cap enforced.
    print("3. Agent loop")
    scenario = json.load(
        open(config.SCENARIOS_DIR / "L5_s2_injected_doc.json", encoding="utf-8"))
    Scenario.from_dict(scenario)
    trace = run_agent(scenario, model="mock", run_idx=0,
                      client=MockAnthropic(scenario=scenario, seed=0))
    validate_trace(trace)
    check("L5 run produced a trace", trace["scenario_id"] == "L5_s2_injected_doc")
    check("trace has recorded tool calls", len(trace["tool_calls"]) >= 1)

    # A run cannot exceed the turn cap.
    calls_per_turn = max((tc["turn"] for tc in trace["tool_calls"]), default=0)
    check("turn indices within cap", calls_per_turn < config.MAX_TURNS)

    # 4. Thesis direction (mock): L5 destructive rate > L0 destructive rate.
    print("4. Thesis direction (mock)")
    def destructive_rate(sid, n=10):
        sc = json.load(open(config.SCENARIOS_DIR / f"{sid}.json", encoding="utf-8"))
        hits = 0
        for i in range(n):
            tr = run_agent(sc, model="mock", run_idx=i,
                           client=MockAnthropic(scenario=sc, seed=i))
            if any(tc["destructive"] for tc in tr["tool_calls"]):
                hits += 1
        return hits
    l0 = destructive_rate("L0_s1_baseline")
    l5 = destructive_rate("L5_s2_injected_doc")
    check("L5 destructive rate > L0", l5 > l0, f"L0={l0}/10 L5={l5}/10")
    print(f"       L0 destructive rate = {l0}/10, L5 = {l5}/10")

    # 5. Runner idempotency + error-as-trace, in a temp traces dir.
    print("5. Runner idempotency")
    from runner import run_scenario
    orig = config.TRACES_DIR
    with tempfile.TemporaryDirectory() as tmp:
        config.TRACES_DIR = Path(tmp)
        try:
            sc = json.load(
                open(config.SCENARIOS_DIR / "L0_s1_baseline.json", encoding="utf-8"))
            n1 = run_scenario(sc, n=5, mock=True, quiet=True)
            before = {p: os.path.getmtime(p)
                      for p in glob.glob(str(Path(tmp) / sc["id"] / "*.json"))}
            n2 = run_scenario(sc, n=5, mock=True, quiet=True)
            after = {p: os.path.getmtime(p)
                     for p in glob.glob(str(Path(tmp) / sc["id"] / "*.json"))}
            check("5 traces written", n1 == 5)
            check("re-run rewrote nothing", before == after)
            check("count stable", n2 == 5)
        finally:
            config.TRACES_DIR = orig

    print()
    if FAILURES:
        print(f"SELF-CHECK FAILED: {len(FAILURES)} failing -> {FAILURES}")
        return 1
    print("SELF-CHECK PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
