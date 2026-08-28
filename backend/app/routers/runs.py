"""
routers/runs.py — Sandbox execution + results
POST   /api/runs/start/{agent_id}      → Run all scenarios (N trials each, auto-classifies)
GET    /api/runs/{run_id}              → Get a single run result
GET    /api/runs/agent/{agent_id}      → Get all runs for an agent
GET    /api/runs/variance/{agent_id}   → Per-scenario pass rate + flakiness across trials
GET    /api/runs/compare/{agent_id}    → Version-over-version regression diff
"""

import asyncio
import os
from datetime import datetime

from fastapi import APIRouter, HTTPException
from bson import ObjectId
from app.database import runs_col, scenarios_col, agents_col
from app.models.agent import AgentConfig
from app.models.scenario import Scenario
from app.services.sandbox import run_scenario
from app.services.failure_classifier import classify_failure

router = APIRouter()

# Max scenarios executed concurrently. Bounds simultaneous Gemini calls so the
# batch doesn't trip rate limits (each run itself makes several sequential
# Gemini calls). Override with the MAX_CONCURRENT_RUNS env var.
MAX_CONCURRENT_RUNS = int(os.getenv("MAX_CONCURRENT_RUNS", "4"))

# Hard cap on trials-per-scenario so one request can't fan out unboundedly.
MAX_TRIALS = int(os.getenv("MAX_TRIALS", "20"))


def serialize(doc: dict) -> dict:
    doc["id"] = str(doc.pop("_id"))
    return doc


def _fm_str(value) -> str:
    """Normalise a failure_mode (enum or already a string) to its string value."""
    return value.value if hasattr(value, "value") else str(value)


def _aggregate_variance(runs: list[dict]) -> list[dict]:
    """Group runs by scenario and compute pass rate + a flakiness score.

    flakiness = 1 - |passed - failed| / trials
      0.0  -> perfectly consistent (all trials agree)
      1.0  -> maximally flaky (50/50 split on identical input)
    """
    by_scen: dict[str, dict] = {}
    for r in runs:
        sid = r.get("scenario_id")
        g = by_scen.setdefault(sid, {
            "scenario_id": sid,
            "scenario_type": r.get("scenario_type"),
            "trials": 0, "passed": 0, "failed": 0, "failure_modes": {},
        })
        g["trials"] += 1
        if r.get("passed"):
            g["passed"] += 1
        else:
            g["failed"] += 1
        fm = _fm_str(r.get("failure_mode", "UNKNOWN"))
        g["failure_modes"][fm] = g["failure_modes"].get(fm, 0) + 1

    out = []
    for g in by_scen.values():
        n = g["trials"] or 1
        g["pass_rate"] = round(g["passed"] / n, 4)
        g["flakiness"] = round(1 - abs(g["passed"] - g["failed"]) / n, 4)
        out.append(g)
    # Flakiest first — that's what a reviewer wants to see.
    out.sort(key=lambda x: x["flakiness"], reverse=True)
    return out


def _majority_by_scenario(runs: list[dict]) -> dict[str, bool]:
    """For each scenario, did it pass in the majority of its trials? (ties -> pass)"""
    agg: dict[str, list[int]] = {}
    for r in runs:
        sid = r.get("scenario_id")
        a = agg.setdefault(sid, [0, 0])  # [passed, failed]
        if r.get("passed"):
            a[0] += 1
        else:
            a[1] += 1
    return {sid: (p >= f) for sid, (p, f) in agg.items()}


@router.post("/start/{agent_id}")
async def start_run(agent_id: str, trials: int = 1):
    """Run every scenario `trials` times (default 1). N>1 surfaces variance —
    the same input producing different behaviour — reported as a flakiness score
    per scenario (and via GET /runs/variance)."""
    trials = max(1, min(trials, MAX_TRIALS))

    # Fetch agent
    agent_doc = await agents_col().find_one({"_id": ObjectId(agent_id)})
    if not agent_doc:
        raise HTTPException(status_code=404, detail="Agent not found")

    agent = AgentConfig(**{k: v for k, v in agent_doc.items() if k != "_id"})

    # Fetch scenarios for this agent
    scenario_docs = await scenarios_col().find({"agent_id": agent_id}).to_list(length=100)
    if not scenario_docs:
        raise HTTPException(status_code=400, detail="No scenarios found. Generate scenarios first.")

    sem = asyncio.Semaphore(MAX_CONCURRENT_RUNS)

    async def _run_one(sdoc: dict, trial_idx: int) -> dict:
        scenario = Scenario(**{k: v for k, v in sdoc.items() if k != "_id"})
        scenario_id = str(sdoc["_id"])

        # Gate the LLM-heavy work (sandbox loop + classifier) behind the
        # semaphore so at most MAX_CONCURRENT_RUNS hit Gemini at once.
        async with sem:
            run_result = await run_scenario(agent, scenario)
            run_result.scenario_id = scenario_id
            run_result.agent_id = agent_id
            classification = await classify_failure(run_result, scenario.description)

        run_result.failure_mode = classification["failure_mode"]
        run_result.failure_reason = classification["reasoning"]

        # Persist run (cheap; outside the semaphore)
        data = run_result.model_dump()
        data["scenario_type"] = scenario.scenario_type.value
        data["classifier_confidence"] = classification["confidence"]
        data["key_evidence"] = classification["key_evidence"]
        data["trial_idx"] = trial_idx
        data["agent_version"] = agent.version
        insert = await runs_col().insert_one(data)
        data["id"] = str(insert.inserted_id)
        data.pop("_id", None)
        return data

    # One task per (scenario, trial); executed concurrently and bounded.
    tasks = [_run_one(sdoc, t) for sdoc in scenario_docs for t in range(trials)]
    results = list(await asyncio.gather(*tasks))

    return {
        "agent_id": agent_id,
        "agent_version": agent.version,
        "trials": trials,
        "total_runs": len(results),
        "passed": sum(1 for r in results if r.get("passed")),
        "failed": sum(1 for r in results if not r.get("passed")),
        "scenario_stats": _aggregate_variance(results),
        "runs": results,
    }


@router.get("/agent/{agent_id}")
async def get_runs_for_agent(agent_id: str):
    cursor = runs_col().find({"agent_id": agent_id})
    docs = await cursor.to_list(length=500)
    return [serialize(d) for d in docs]


@router.get("/variance/{agent_id}")
async def get_variance(agent_id: str):
    """Per-scenario pass rate and flakiness across all stored trials."""
    docs = await runs_col().find({"agent_id": agent_id}).to_list(length=2000)
    stats = _aggregate_variance(docs)
    return {
        "agent_id": agent_id,
        "total_runs": len(docs),
        "flaky_count": sum(1 for s in stats if s["flakiness"] > 0),
        "scenarios": stats,
    }


@router.get("/compare/{agent_id}")
async def compare_versions(
    agent_id: str,
    base_version: str | None = None,
    head_version: str | None = None,
):
    """Regression diff between two agent versions: which scenarios newly pass or
    fail. Versions default to the two most recent seen in the run history."""
    docs = await runs_col().find({"agent_id": agent_id}).to_list(length=5000)
    if not docs:
        raise HTTPException(status_code=400, detail="No runs found for this agent.")

    # Order versions by most-recent run time.
    ver_time: dict[str, datetime] = {}
    for d in docs:
        v = d.get("agent_version", "unknown")
        t = d.get("created_at")
        if isinstance(t, str):
            t = None
        if v not in ver_time or (t and (ver_time[v] is None or t > ver_time[v])):
            ver_time[v] = t
    versions_sorted = sorted(ver_time, key=lambda v: (ver_time[v] or datetime.min))

    head_version = head_version or (versions_sorted[-1] if versions_sorted else "unknown")
    if base_version is None:
        base_version = versions_sorted[-2] if len(versions_sorted) >= 2 else head_version

    if base_version == head_version:
        return {
            "agent_id": agent_id, "base_version": base_version, "head_version": head_version,
            "available_versions": versions_sorted,
            "note": "Need runs from two different agent versions to compare. "
                    "Bump the agent version and re-run.",
            "summary": {"regressed": 0, "improved": 0, "unchanged": 0, "new": 0, "removed": 0},
            "regressed": [], "improved": [], "unchanged": [], "new": [], "removed": [],
        }

    base_out = _majority_by_scenario([d for d in docs if d.get("agent_version", "unknown") == base_version])
    head_out = _majority_by_scenario([d for d in docs if d.get("agent_version", "unknown") == head_version])

    scen_docs = await scenarios_col().find({"agent_id": agent_id}).to_list(length=500)
    title = {str(s["_id"]): s.get("title", "") for s in scen_docs}

    regressed, improved, unchanged, new_, removed = [], [], [], [], []
    for sid in set(base_out) | set(head_out):
        entry = {"scenario_id": sid, "title": title.get(sid, sid)}
        b, h = base_out.get(sid), head_out.get(sid)
        if b is None:
            new_.append(entry)
        elif h is None:
            removed.append(entry)
        elif b and not h:
            regressed.append(entry)
        elif (not b) and h:
            improved.append(entry)
        else:
            unchanged.append({**entry, "passed": h})

    return {
        "agent_id": agent_id,
        "base_version": base_version,
        "head_version": head_version,
        "available_versions": versions_sorted,
        "summary": {
            "regressed": len(regressed), "improved": len(improved),
            "unchanged": len(unchanged), "new": len(new_), "removed": len(removed),
        },
        "regressed": regressed, "improved": improved,
        "unchanged": unchanged, "new": new_, "removed": removed,
    }


@router.get("/{run_id}")
async def get_run(run_id: str):
    doc = await runs_col().find_one({"_id": ObjectId(run_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Run not found")
    return serialize(doc)
