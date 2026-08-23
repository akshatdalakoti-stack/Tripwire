"""
main.py — FastAPI application entry point.
Registers all routers, CORS middleware, and DB lifecycle.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import connect_db, close_db

# ── Routers (imported after DB is set up) ─────────────────
from app.routers import agents, scenarios, runs, classifier, guardrails, scorecard


# ── Lifespan ──────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.validate()
    await connect_db()
    yield
    await close_db()


# ── App ───────────────────────────────────────────────────
app = FastAPI(
    title="Tripwire API",
    description="AI Agent Evaluation and Reliability Engine",
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.CORS_ORIGINS.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    return {"status": "ok", "service": "Tripwire", "version": "1.0.0"}


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "healthy"}
