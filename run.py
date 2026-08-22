"""Step 8 - One-command reproducibility.

A clean clone + an API key + one command reproduces every number in the README.

    python run.py --all          # scenarios -> traces -> analysis -> chart
    python run.py --level 5      # one pressure level, then analysis
    python run.py --replay <trace>
    python run.py --all --mock   # full offline dry-run, zero API calls

The analysis + chart half belongs to Member B. This entrypoint calls their
analysis via a single agreed function; if it is not present yet, the trace
generation still runs and a clear note is printed. The one coordination point
is the analysis function signature (see `_run_analysis` below) -- agree it once,
then keep the two halves decoupled.
"""
from __future__ import annotations

import argparse
import sys

import config
from batch import run_matrix


def _run_analysis() -> bool:
    """Call Member B's analysis entrypoint. Returns True if it ran.

    Convention (coordinate this signature once with Member B):
        analysis/analyze.py  ->  run_analysis(traces_dir, analysis_dir)
    """
    # Make ps4/analysis importable as a package-free module.
    sys.path.insert(0, str(config.ANALYSIS_DIR))
    try:
        import analyze  # type: ignore
    except ModuleNotFoundError:
        print(
            "\n[analysis] analysis/analyze.py not found yet -- that is "
            "Member B's half.\n"
            "           Traces are on disk in ./traces and ready to consume.\n"
            "           Agreed entrypoint: analyze.run_analysis(traces_dir, "
            "analysis_dir).",
            file=sys.stderr,
        )
        return False

    fn = getattr(analyze, "run_analysis", None)
    if fn is None:
        print("[analysis] analyze.py has no run_analysis(traces_dir, "
              "analysis_dir) -- skipping.", file=sys.stderr)
        return False

    print("\n[analysis] handing off to Member B's analyze.run_analysis(...)")
    fn(str(config.TRACES_DIR), str(config.ANALYSIS_DIR))
    return True


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description="Tripwire: one-command reproduction (Member A entrypoint)."
    )
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--all", action="store_true",
                   help="run the full matrix, then analysis")
    g.add_argument("--level", type=int, metavar="N",
                   help="run one pressure level (0-5), then analysis")
    g.add_argument("--replay", metavar="TRACE",
                   help="replay a single saved trace offline")
    p.add_argument("--n", type=int, default=config.DEFAULT_TRIALS,
                   help=f"trials per scenario (default {config.DEFAULT_TRIALS})")
    p.add_argument("--force", action="store_true",
                   help="re-run even if trace files already exist")
    p.add_argument("--mock", action="store_true",
                   help="run offline against the deterministic mock client")
    args = p.parse_args(argv)

    if args.replay:
        from replay import replay

        replay(args.replay)
        return 0

    mock = True if args.mock else None
    level = None if args.all else args.level
    run_matrix(n=args.n, force=args.force, level=level, mock=mock)
    _run_analysis()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
