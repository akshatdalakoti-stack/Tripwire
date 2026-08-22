"""Central configuration for the Tripwire harness (Member A).

Everything that varies between machines or runs lives here so the rest of the
code never hard-codes a path or a model id.
"""
from __future__ import annotations

import os
from pathlib import Path

# --- Paths -----------------------------------------------------------------
# All paths are resolved relative to this file, so the harness works no matter
# what the current working directory is when a script is launched.
ROOT = Path(__file__).resolve().parent
SCENARIOS_DIR = ROOT / "scenarios"
TRACES_DIR = ROOT / "traces"
FIXTURES_DIR = ROOT / "fixtures"
ANALYSIS_DIR = ROOT / "analysis"

# --- Model under test ------------------------------------------------------
# The build guide is explicit: use a *cheap, fast* model for the agent under
# test, because a full matrix is ~240 multi-turn conversations. Claude Haiku
# 4.5 is the cheapest/fastest current model. Override with PS4_MODEL if you
# want to probe a different model (that is a legitimate experiment axis).
MODEL = os.environ.get("PS4_MODEL", "claude-haiku-4-5")

# Per-response token cap for the SUT. Agent turns are short; 1024 is plenty
# and keeps cost down.
MAX_TOKENS = int(os.environ.get("PS4_MAX_TOKENS", "1024"))

# Hard turn cap for the agent loop. An agent stuck in a tool-call loop can
# otherwise burn hundreds of calls on a single run. Hitting this cap is the
# DERAILED outcome Member B classifies.
MAX_TURNS = int(os.environ.get("PS4_MAX_TURNS", "8"))

# --- Batch tuning ----------------------------------------------------------
# 4-6 workers is the sweet spot: more trips rate limits and the backoff costs
# more wall-clock than the extra parallelism buys.
BATCH_WORKERS = int(os.environ.get("PS4_WORKERS", "5"))
DEFAULT_TRIALS = int(os.environ.get("PS4_TRIALS", "10"))

# --- Offline / mock mode ---------------------------------------------------
# When PS4_MOCK is truthy (or --mock is passed on the CLI), the harness runs
# against a deterministic fake client instead of the live API. This makes ZERO
# network requests and costs nothing. It exists so the whole pipeline
# (agent -> runner -> batch -> replay) can be exercised and demoed offline.
# NOTE: real experiment data MUST be generated against the live model. Mock
# traces are stamped with a model id of "mock" so they can never be confused
# with real runs.
def mock_enabled() -> bool:
    return os.environ.get("PS4_MOCK", "").lower() in ("1", "true", "yes", "on")
