"""Step 6 - Batch: the full matrix. This is the overnight job.

6 pressure levels x 4 scenarios x 10 trials = 240 multi-turn agent runs (with
the full scenario set). Wall-clock time is the binding constraint, so start it
early.

Design:
  * Concurrency via ThreadPoolExecutor, 4-6 workers. More trips rate limits and
    the backoff costs more time than the parallelism buys.
  * Progress to stdout as each run finishes, so a stalled job is visible without
    a debugger.
  * Resumable by construction: Step 4 skips existing files, so a killed batch
    resumes by re-running the exact same command.
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional

import config
from agent import error_trace, get_client, run_agent
from runner import _write_trace_atomic, _rate_limit_exc_types, _sleep_with_backoff
from schemas import Scenario

_print_lock = threading.Lock()


def _log(msg: str) -> None:
    with _print_lock:
        print(msg, flush=True)


def discover_scenarios(
    scenarios_dir: Path = config.SCENARIOS_DIR, level: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Load and validate every scenario JSON file, optionally one level only."""
    scenarios: List[Dict[str, Any]] = []
    for path in sorted(scenarios_dir.glob("*.json")):
        try:
            with open(path, encoding="utf-8") as f:
                sc = json.load(f)
            Scenario.from_dict(sc)  # validate
        except Exception as e:
            _log(f"[skip] {path.name}: {e}")
            continue
        if level is not None and int(sc["pressure_level"]) != level:
            continue
        scenarios.append(sc)
    return scenarios


def _run_one(
    scenario: Dict[str, Any], run_idx: int, model: str, use_mock: bool
) -> Dict[str, Any]:
    """Execute a single (scenario, run_idx) cell, with rate-limit backoff.

    Returns the trace dict (which may be an error trace) that was written.
    """
    out_dir = config.TRACES_DIR / scenario["id"]
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"run_{run_idx:02d}.json"

    effective_model = "mock" if use_mock else model
    rate_limit_types = _rate_limit_exc_types()

    attempt = 0
    while True:
        client = get_client(mock=use_mock, scenario=scenario, seed=run_idx)
        try:
            trace = run_agent(
                scenario, model=effective_model, run_idx=run_idx, client=client
            )
            break
        except rate_limit_types:  # type: ignore[misc]
            attempt += 1
            if attempt > 8:
                trace = error_trace(
                    scenario, run_idx, RuntimeError("rate-limited, gave up"),
                    effective_model,
                )
                break
            _sleep_with_backoff(attempt)
        except Exception as e:
            trace = error_trace(scenario, run_idx, e, effective_model)
            break

    _write_trace_atomic(path, trace)
    return trace


def run_matrix(
    n: int = config.DEFAULT_TRIALS,
    force: bool = False,
    model: str = config.MODEL,
    level: Optional[int] = None,
    workers: int = config.BATCH_WORKERS,
    mock: Optional[bool] = None,
) -> Dict[str, int]:
    """Run every discovered scenario N times, concurrently. Returns a summary."""
    use_mock = config.mock_enabled() if mock is None else mock
    scenarios = discover_scenarios(level=level)
    if not scenarios:
        _log(f"No scenarios found in {config.SCENARIOS_DIR} "
             f"(level filter={level}).")
        return {"scenarios": 0, "planned": 0, "executed": 0, "skipped": 0}

    # Build the work list, honouring idempotency up front.
    work = []
    skipped = 0
    for sc in scenarios:
        out_dir = config.TRACES_DIR / sc["id"]
        for i in range(n):
            path = out_dir / f"run_{i:02d}.json"
            if path.exists() and not force:
                skipped += 1
                continue
            work.append((sc, i))

    total = len(scenarios) * n
    _log(f"Matrix: {len(scenarios)} scenarios x {n} trials = {total} runs "
         f"({skipped} already on disk, {len(work)} to run, "
         f"{'MOCK' if use_mock else model}, {workers} workers)")

    executed = 0
    done = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(_run_one, sc, i, model, use_mock): (sc["id"], i)
            for sc, i in work
        }
        for fut in as_completed(futures):
            sid, i = futures[fut]
            done += 1
            try:
                trace = fut.result()
                state = trace["terminal_state"]
                nd = sum(1 for tc in trace["tool_calls"] if tc["destructive"])
                _log(f"[{done}/{len(work)}] {sid} run {i:02d} -> {state} "
                     f"(destructive={nd})")
            except Exception as e:  # a future should never raise, but be safe
                _log(f"[{done}/{len(work)}] {sid} run {i:02d} -> FAILED {e}")
            executed += 1

    on_disk = sum(
        len(list((config.TRACES_DIR / sc["id"]).glob("run_*.json")))
        for sc in scenarios
    )
    _log(f"\nDone. {on_disk} trace files across "
         f"{len(scenarios)} scenario director"
         f"{'y' if len(scenarios) == 1 else 'ies'}.")
    return {
        "scenarios": len(scenarios),
        "planned": total,
        "executed": executed,
        "skipped": skipped,
        "on_disk": on_disk,
    }


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Run the full scenario x trial matrix.")
    p.add_argument("--n", type=int, default=config.DEFAULT_TRIALS,
                   help=f"trials per scenario (default {config.DEFAULT_TRIALS})")
    p.add_argument("--level", type=int, default=None,
                   help="only run scenarios at this pressure level (0-5)")
    p.add_argument("--force", action="store_true",
                   help="re-run even if trace files already exist")
    p.add_argument("--workers", type=int, default=config.BATCH_WORKERS,
                   help=f"concurrent workers (default {config.BATCH_WORKERS})")
    p.add_argument("--model", default=config.MODEL,
                   help=f"model id (default {config.MODEL})")
    p.add_argument("--mock", action="store_true",
                   help="run offline against the deterministic mock client")
    return p


def main(argv=None) -> int:
    args = _build_arg_parser().parse_args(argv)
    mock = True if args.mock else None
    run_matrix(
        n=args.n, force=args.force, model=args.model,
        level=args.level, workers=args.workers, mock=mock,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
