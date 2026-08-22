"""Step 4 - Runner: turn one scenario into N trace files on disk.

The whole reason for N > 1 is variance: identical input, different behaviour.
That variance is the project's answer to "why not just test the agent by hand?"

Two properties are non-negotiable and both are cheap:
  * Idempotency  - skip runs whose trace file already exists, so re-running the
                   matrix does not re-spend quota on completed work.
  * Errors-as-traces - an exception mid-run is written out as a trace with
                   terminal_state "error", never allowed to crash the batch.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from pathlib import Path
from typing import Any, Dict

import config
from agent import error_trace, get_client, run_agent
from schemas import Scenario, validate_trace


def _load_scenario(path: str) -> Dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        scenario = json.load(f)
    Scenario.from_dict(scenario)  # validate; raises SchemaError on a bad file
    return scenario


def _rate_limit_exc_types():
    """Return the exception types that mean 'back off and retry'.

    Imported lazily so the harness runs in mock mode without `anthropic`
    installed.
    """
    try:
        import anthropic

        return (anthropic.RateLimitError, anthropic.APIConnectionError)
    except Exception:  # pragma: no cover - anthropic not installed
        return tuple()


def _sleep_with_backoff(attempt: int) -> None:
    # Exponential backoff with jitter, capped.
    delay = min(60.0, (2 ** attempt)) + random.uniform(0, 1.0)
    time.sleep(delay)


def run_scenario(
    scenario: Dict[str, Any],
    n: int = config.DEFAULT_TRIALS,
    force: bool = False,
    model: str = config.MODEL,
    mock: bool | None = None,
    quiet: bool = False,
) -> int:
    """Run `scenario` `n` times, writing traces/<id>/run_XX.json.

    Returns the number of trace files that exist for this scenario afterwards.
    """
    out_dir = config.TRACES_DIR / scenario["id"]
    out_dir.mkdir(parents=True, exist_ok=True)

    use_mock = config.mock_enabled() if mock is None else mock
    effective_model = "mock" if use_mock else model
    rate_limit_types = _rate_limit_exc_types()

    i = 0
    while i < n:
        path = out_dir / f"run_{i:02d}.json"
        if path.exists() and not force:
            i += 1
            continue  # <- idempotency: never re-spend quota on completed work

        client = get_client(mock=use_mock, scenario=scenario, seed=i)
        try:
            trace = run_agent(
                scenario, model=effective_model, run_idx=i, client=client
            )
        except rate_limit_types:  # type: ignore[misc]
            if not quiet:
                print(f"  [rate-limit] {scenario['id']} run {i}, backing off",
                      file=sys.stderr)
            _sleep_with_backoff(attempt=min(i, 6))
            continue  # retry the same index; do NOT advance i
        except Exception as e:  # errors become traces, not crashes
            trace = error_trace(scenario, i, e, effective_model)
            if not quiet:
                print(f"  [error] {scenario['id']} run {i}: {e}", file=sys.stderr)

        _write_trace_atomic(path, trace)
        if not quiet:
            state = trace["terminal_state"]
            nd = sum(1 for tc in trace["tool_calls"] if tc["destructive"])
            print(f"  {scenario['id']} run {i:02d} -> {state} "
                  f"(destructive={nd})")
        i += 1

    return len(list(out_dir.glob("run_*.json")))


def _write_trace_atomic(path: Path, trace: Dict[str, Any]) -> None:
    """Validate then write, via a temp file, so a half-written trace is never
    left on disk if the process is killed mid-write."""
    validate_trace(trace)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(trace, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Run one scenario N times and write traces to disk."
    )
    p.add_argument("scenario", help="path to a scenario JSON file")
    p.add_argument("--n", type=int, default=config.DEFAULT_TRIALS,
                   help=f"number of trials (default {config.DEFAULT_TRIALS})")
    p.add_argument("--force", action="store_true",
                   help="re-run even if trace files already exist")
    p.add_argument("--model", default=config.MODEL,
                   help=f"model id (default {config.MODEL})")
    p.add_argument("--mock", action="store_true",
                   help="run offline against the deterministic mock client")
    return p


def main(argv=None) -> int:
    args = _build_arg_parser().parse_args(argv)
    scenario = _load_scenario(args.scenario)
    mock = True if args.mock else None
    count = run_scenario(
        scenario, n=args.n, force=args.force, model=args.model, mock=mock
    )
    print(f"\n{count} trace(s) in {config.TRACES_DIR / scenario['id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
