"""
main.py — FastAPI application entry point.
Registers all routers, CORS middleware, and DB lifecycle.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.config import settings
from app.database import connect_db, close_db, get_db, get_redis

# ── Routers (imported after DB is set up) ─────────────────
from app.routers import agents, scenarios, runs, classifier, guardrails, scorecard
from app.services.job_manager import mark_interrupted_jobs
from app.utils import gemini_client

VERSION = "2.0.0"


# ── Lifespan ──────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.validate()
    await connect_db()
    try:
        await mark_interrupted_jobs()
    except Exception:
        pass
    if settings.MOCK_LLM:
        print("MOCK_LLM is on — using the offline mock model, no Gemini calls will be made.")
    yield
    await close_db()


# ── App ───────────────────────────────────────────────────
app = FastAPI(
    title="Tripwire API",
    description="AI Agent Evaluation and Reliability Engine",
    version=VERSION,
    lifespan=lifespan,
)

# ── Middleware ────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.CORS_ORIGINS.split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Run lists with traces get big; compress them. Starlette never gzips text/event-stream,
# so the live SSE feed is unaffected.
app.add_middleware(GZipMiddleware, minimum_size=2048)

# ── Routes ────────────────────────────────────────────────
app.include_router(agents.router,      prefix="/api/agents",      tags=["Agents"])
app.include_router(scenarios.router,   prefix="/api/scenarios",   tags=["Scenarios"])
app.include_router(runs.router,        prefix="/api/runs",        tags=["Runs"])
app.include_router(classifier.router,  prefix="/api/classify",    tags=["Classifier"])
app.include_router(guardrails.router,  prefix="/api/guardrails",  tags=["Guardrails"])
app.include_router(scorecard.router,   prefix="/api/scorecard",   tags=["Scorecard"])


# ── Health ────────────────────────────────────────────────
@app.get("/", tags=["Health"])
async def root():
    return {"status": "ok", "service": "Tripwire", "version": VERSION}


@app.get("/health", tags=["Health"])
async def health():
    mongo_ok = True
    try:
        await get_db().command("ping")
    except Exception:
        mongo_ok = False
    return {
        "status": "healthy" if mongo_ok else "degraded",
        "mongo": mongo_ok,
        "redis": get_redis() is not None,
        "llm": {"model": "mock" if settings.MOCK_LLM else gemini_client.MODEL, **gemini_client.stats},
    }


@app.get("/api/meta", tags=["Health"])
async def meta():
    """Lets the UI show which model/mode the backend is in."""
    return {
        "version": VERSION,
        "mock_llm": settings.MOCK_LLM,
        "model": "mock" if settings.MOCK_LLM else gemini_client.MODEL,
        "max_trials": settings.MAX_TRIALS,
        "max_scenarios_per_generation": settings.MAX_SCENARIOS_PER_GENERATION,
        # Measured average LLM calls per scenario run (sandbox steps + classifier).
        "llm_calls_per_run": 4,
        # 429 responses seen recently — the UI warns that new results may contain errored runs.
        "rate_limits_last_15m": gemini_client.recent_rate_limits(900),
        # Gemini free tier, measured 2026-11-25 (see LIMITATIONS.md). Not enforced; shown as guidance.
        "free_tier": {"requests_per_minute": 5, "requests_per_day": 20},
    }
