"""
config.py — Centralized environment variable loader.
All settings are read from .env via python-dotenv.
"""

import os
from dotenv import load_dotenv

load_dotenv()


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


class Settings:
    # ── LLM ──────────────────────────────────────────────
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
    # Tried once when the primary model is overloaded / rate limited.
    GEMINI_FALLBACK_MODEL: str = os.getenv("GEMINI_FALLBACK_MODEL", "")
    # Max simultaneous Gemini requests across the whole process.
    LLM_MAX_CONCURRENCY: int = _env_int("LLM_MAX_CONCURRENCY", 6)
    # Retries (with exponential backoff) on 429 / 5xx.
    LLM_MAX_RETRIES: int = _env_int("LLM_MAX_RETRIES", 3)
    # Deterministic offline LLM — no API key needed. For demos, CI and tests.
    MOCK_LLM: bool = _env_bool("MOCK_LLM", False)
    # Mock only: fraction of calls that fail with a simulated 429, to test how
    # infrastructure errors are handled without spending real quota.
    MOCK_LLM_ERROR_RATE: float = float(os.getenv("MOCK_LLM_ERROR_RATE", "0") or 0)

    # ── Storage ──────────────────────────────────────────
    MONGODB_URI: str = os.getenv("MONGO_URI", "mongodb://localhost:27017/tripwire")
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    DB_NAME: str = os.getenv("DB_NAME", "tripwire")

    # ── Execution ────────────────────────────────────────
    MAX_CONCURRENT_RUNS: int = _env_int("MAX_CONCURRENT_RUNS", 4)
    MAX_TRIALS: int = _env_int("MAX_TRIALS", 20)
    MAX_SCENARIOS_PER_GENERATION: int = _env_int("MAX_SCENARIOS_PER_GENERATION", 25)
    # Ask the LLM classifier to double-check runs the sandbox thinks passed
    # (catches GOAL_DRIFT / HALLUCINATED_CONFIDENCE). Costs one call per pass.
    CLASSIFY_PASSES: bool = _env_bool("CLASSIFY_PASSES", True)
    # Use one batched LLM call to judge guardrail responses (falls back to heuristics).
    GUARDRAIL_LLM_JUDGE: bool = _env_bool("GUARDRAIL_LLM_JUDGE", True)

    # ── App ──────────────────────────────────────────────
    APP_PORT: int = _env_int("APP_PORT", 8000)
    APP_ENV: str = os.getenv("APP_ENV", "development")
    CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000")

    def validate(self):
        if not self.GEMINI_API_KEY and not self.MOCK_LLM:
            raise ValueError("GEMINI_API_KEY is not set in .env (or set MOCK_LLM=1 to run offline)")


settings = Settings()
