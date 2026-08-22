"""Step 2 - The System-Under-Test (SUT) agent loop.

Deliberately minimal and deliberately weak. Resist every instinct to improve
it: the agent's weakness IS the product's content. A hardened agent produces a
flat, boring chart and there is nothing to report.

The loop is a raw message loop we wrote ourselves -- no LangChain, no CrewAI.
Frameworks hide the tool loop, and the tool loop is the exact thing we are
instrumenting.
"""
from __future__ import annotations

import datetime as _dt
from typing import Any, Dict, List, Optional

import config
from schemas import Trace
from tools import MockToolRegistry, UnknownToolError, tool_specs


# ---------------------------------------------------------------------------
# Client factory
# ---------------------------------------------------------------------------
def get_client(
    mock: Optional[bool] = None,
    scenario: Optional[Dict[str, Any]] = None,
    seed: int = 0,
):
    """Return a client exposing `.messages.create(...)`.

    Live mode returns a real `anthropic.Anthropic()`. Mock mode returns a
    deterministic offline client (see mockclient.py) that makes zero network
    requests -- used for tests and offline demos only. `scenario` and `seed`
    are ignored in live mode; in mock mode they give per-run variance.
    """
    use_mock = config.mock_enabled() if mock is None else mock
    if use_mock:
        from mockclient import MockAnthropic

        return MockAnthropic(scenario=scenario, seed=seed)
    import anthropic

    return anthropic.Anthropic()


def _utc_now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _block_to_dict(block: Any) -> Dict[str, Any]:
    """Serialize one response content block to a plain JSON-safe dict.

    Handles both real SDK blocks (pydantic, have `.model_dump`) and the mock
    client's blocks (also expose `.model_dump`).
    """
    if hasattr(block, "model_dump"):
        return block.model_dump(mode="json", exclude_none=True)
    if isinstance(block, dict):
        return block
    # Last-resort best effort.
    return {"type": getattr(block, "type", "unknown"), "repr": repr(block)}


def _serialize_messages(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Deep-convert a live `messages` list into JSON-serialisable dicts.

    Assistant turns hold SDK block objects; everything else is already plain.
    """
    out: List[Dict[str, Any]] = []
    for msg in messages:
        content = msg.get("content")
        if isinstance(content, list):
            content = [
                _block_to_dict(b) if not isinstance(b, dict) else b
                for b in content
            ]
        out.append({"role": msg["role"], "content": content})
    return out


def build_trace(
    scenario: Dict[str, Any],
    messages: List[Dict[str, Any]],
    tool_calls: List[Dict[str, Any]],
    state: str,
    run_idx: int,
    model: str,
) -> Dict[str, Any]:
    """Assemble the on-disk trace dict.

    The stored `messages` are self-contained: the system prompt is prepended as
    a synthetic `{"role": "system"}` entry so replay.py can render the full
    conversation offline (the live API call passes `system` separately).
    """
    stored = [{"role": "system", "content": scenario["system_prompt"]}]
    stored.extend(_serialize_messages(messages))

    trace = Trace(
        scenario_id=scenario["id"],
        run_idx=run_idx,
        model=model,
        timestamp=_utc_now_iso(),
        messages=stored,
        tool_calls=tool_calls,
        terminal_state=state,
    )
    return trace.to_dict()


def error_trace(
    scenario: Dict[str, Any], run_idx: int, exc: Exception, model: str
) -> Dict[str, Any]:
    """Turn a mid-run exception into a trace instead of losing the run.

    A crashed batch that drops 200 completed runs because run 201 threw is the
    classic way this project dies overnight. Errors become data.
    """
    trace = Trace(
        scenario_id=scenario.get("id", "<unknown>"),
        run_idx=run_idx,
        model=model,
        timestamp=_utc_now_iso(),
        messages=[{"role": "system", "content": scenario.get("system_prompt", "")}],
        tool_calls=[],
        terminal_state="error",
        error=f"{type(exc).__name__}: {exc}",
    )
    return trace.to_dict()


def run_agent(
    scenario: Dict[str, Any],
    model: str = config.MODEL,
    max_turns: int = config.MAX_TURNS,
    run_idx: int = 0,
    client: Any = None,
) -> Dict[str, Any]:
    """Run one agent conversation end to end and return a trace dict."""
    if client is None:
        client = get_client(scenario=scenario, seed=run_idx)

    reg = MockToolRegistry(scenario.get("injected_tool_outputs"))
    # Copy the scenario turns so we never mutate Member B's scenario dict.
    messages: List[Dict[str, Any]] = [dict(t) for t in scenario["turns"]]
    specs = tool_specs(scenario["tools"])
    state = "completed"

    for turn in range(max_turns):
        resp = client.messages.create(
            model=model,
            max_tokens=config.MAX_TOKENS,
            system=scenario["system_prompt"],
            tools=specs,
            messages=messages,
        )

        messages.append({"role": "assistant", "content": resp.content})

        if resp.stop_reason != "tool_use":
            break

        results = []
        for block in resp.content:
            if getattr(block, "type", None) != "tool_use":
                continue
            try:
                out = reg.call(block.name, block.input, turn)
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": out,
                    }
                )
            except UnknownToolError as e:
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": f"Error: unknown tool {e}.",
                        "is_error": True,
                    }
                )
        messages.append({"role": "user", "content": results})
    else:
        # for/else: the loop finished without `break`, i.e. it hit the turn cap.
        # This is exactly the DERAILED outcome Member B needs.
        state = "turn_cap_hit"

    return build_trace(scenario, messages, reg.calls, state, run_idx, model)


if __name__ == "__main__":
    # Smoke test: run one bundled example scenario and print the trace.
    # Uses mock mode unless a real ANTHROPIC key + live client is wired up.
    import json
    import sys

    from schemas import Scenario

    path = (
        sys.argv[1]
        if len(sys.argv) > 1
        else str(config.SCENARIOS_DIR / "L0_s1_baseline.json")
    )
    scenario = json.loads(open(path, encoding="utf-8").read())
    Scenario.from_dict(scenario)  # validate
    trace = run_agent(scenario, run_idx=0)
    print(json.dumps(trace, indent=2))
    n_destructive = sum(1 for tc in trace["tool_calls"] if tc["destructive"])
    print(
        f"\n[smoke] terminal_state={trace['terminal_state']} "
        f"tool_calls={len(trace['tool_calls'])} destructive={n_destructive}",
        file=sys.stderr,
    )
