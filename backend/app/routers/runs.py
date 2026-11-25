"""
routers/runs.py — Sandbox execution + results
POST   /api/runs/start/{agent_id}       → Run scenarios synchronously (N trials each, auto-classifies)
POST   /api/runs/jobs/{agent_id}        → Start a background run job (returns immediately)
GET    /api/runs/jobs?agent_id=         → Recent jobs (newest first)
GET    /api/runs/jobs/{job_id}          → Job status + counters
GET    /api/runs/jobs/{job_id}/events   → Server-Sent Events: each run as it finishes, progress, done
POST   /api/runs/jobs/{job_id}/cancel   → Cancel a running job
GET    /api/runs/agent/{agent_id}       → Runs for an agent (filterable, traces optional)
DELETE /api/runs/agent/{agent_id}       → Clear an agent's run + score history
GET    /api/runs/variance/{agent_id}    → Per-scenario pass rate + flakiness across trials
GET    /api/runs/compare/{agent_id}     → Version-over-version regression diff
GET    /api/runs/{run_id}               → Get a single run result
"""

import asyncio
import json
from datetime import datetime

from bson import ObjectId
from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.config import settings
from app.database import runs_col, scenarios_col, jobs_col, reports_col
from app.services.job_manager import TERMINAL, cancel_job, start_job
from app.services.run_executor import execute_batch, load_scenarios
from app.utils.ids import parse_object_id, serialize
from app.utils.loaders import load_agent

router = APIRouter()

# Back-compat aliases (some scripts import these from here).
MAX_CONCURRENT_RUNS = settings.MAX_CONCURRENT_RUNS
MAX_TRIALS = settings.MAX_TRIALS


class RunRequest(BaseModel):
    scenario_ids: list[str] | None = None


def _fm_str(value) -> str:
    """Normalise a failure_mode (enum or already a string) to its string value."""
    return value.value if hasattr(value, "value") else str(value)


def _json_default(o):
    if isinstance(o, datetime):
        return o.isoformat()
    if isinstance(o, ObjectId):
        return str(o)
    return str(o)


def _aggregate_variance(runs: list[dict], titles: dict[str, str] | None = None) -> list[dict]:
    """Group runs by scenario and compute pass rate + a flakiness score.

    flakiness = 1 - |passed - failed| / trials
      0.0  -> perfectly consistent (all trials agree)
      1.0  -> maximally flaky (50/50 split on identical input)
    """
    titles = titles or {}
    by_scen: dict[str, dict] = {}
    for r in runs:
        sid = str(r.get("scenario_id"))
        g = by_scen.setdefault(sid, {
            "scenario_id": sid,
            "title": r.get("scenario_title") or titles.get(sid, sid),
            "scenario_type": r.get("scenario_type"),
            "pressure_level": r.get("pressure_level"),
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
    # Flakiest first, then worst pass rate — that's what a reviewer wants to see.
    out.sort(key=lambda x: (-x["flakiness"], x["pass_rate"]))
    return out


def _majority_by_scenario(runs: list[dict]) -> dict[str, bool]:
    """For each scenario, did it pass in the majority of its trials? (ties -> pass)"""
    agg: dict[str, list[int]] = {}
    for r in runs:
        sid = str(r.get("scenario_id"))
        a = agg.setdefault(sid, [0, 0])  # [passed, failed]
        if r.get("passed"):
            a[0] += 1
        else:
            a[1] += 1
    return {sid: (p >= f) for sid, (p, f) in agg.items()}


async def _scenario_titles(agent_id: str) -> dict[str, str]:
    docs = await scenarios_col().find({"agent_id": agent_id}, {"title": 1}).to_list(length=1000)
    return {str(s["_id"]): s.get("title", "") for s in docs}


async def _prepare(agent_id: str, trials: int, req: RunRequest | None):
    trials = max(1, min(trials, settings.MAX_TRIALS))
    agent, _ = await load_agent(agent_id)
    scenario_docs = await load_scenarios(agent_id, req.scenario_ids if req else None)
    if not scenario_docs:
        raise HTTPException(status_code=400, detail="No scenarios found. Generate scenarios first.")
    return agent, scenario_docs, trials


@router.post("/start/{agent_id}")
async def start_run(agent_id: str, trials: int = 1, req: RunRequest | None = Body(default=None)):
    """Run every scenario `trials` times (default 1) and wait for the results.
    N>1 surfaces variance — the same input producing different behaviour —
    reported as a flakiness score per scenario (and via GET /runs/variance).
    For long batches prefer POST /runs/jobs/{agent_id}."""
    agent, scenario_docs, trials = await _prepare(agent_id, trials, req)
    results = await execute_batch(agent, agent_id, scenario_docs, trials)

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


# ── Background jobs ───────────────────────────────────────

@router.post("/jobs/{agent_id}", status_code=202)
async def create_job(agent_id: str, trials: int = 1, req: RunRequest | None = Body(default=None)):
    running = await jobs_col().find_one({"agent_id": agent_id, "status": "running"})
    if running:
        raise HTTPException(status_code=409, detail=f"A run is already in progress for this agent (job {running['_id']}).")
    agent, scenario_docs, trials = await _prepare(agent_id, trials, req)
    return await start_job(agent, agent_id, scenario_docs, trials)


@router.get("/jobs")
async def list_jobs(agent_id: str | None = None, limit: int = 20):
    query = {"agent_id": agent_id} if agent_id else {}
    docs = await jobs_col().find(query).sort("created_at", -1).to_list(length=max(1, min(limit, 100)))
    return [serialize(d) for d in docs]


@router.get("/jobs/{job_id}")
async def get_job(job_id: str):
    doc = await jobs_col().find_one({"_id": parse_object_id(job_id, "job id")})
    if not doc:
        raise HTTPException(status_code=404, detail="Job not found")
    return serialize(doc)


@router.post("/jobs/{job_id}/cancel")
async def cancel(job_id: str):
    parse_object_id(job_id, "job id")
    return {"job_id": job_id, "cancelled": await cancel_job(job_id)}


@router.get("/jobs/{job_id}/events")
async def job_events(job_id: str, request: Request):
    """SSE stream. Events: `run` (a finished run, with trace), `progress`
    (counters), `done` (terminal status). Reconnecting replays all runs, so
    clients should de-duplicate by run id."""
    oid = parse_object_id(job_id, "job id")
    if not await jobs_col().find_one({"_id": oid}, {"_id": 1}):
        raise HTTPException(status_code=404, detail="Job not found")

    def sse(event: str, data) -> str:
        return f"event: {event}\ndata: {json.dumps(data, default=_json_default)}\n\n"

    async def stream():
        seen: list[ObjectId] = []
        last_progress = None
        ticks = 0
        while True:
            if await request.is_disconnected():
                return
            job = await jobs_col().find_one({"_id": oid})
            if not job:
                yield sse("error", {"detail": "Job deleted"})
                return
            new_runs = await runs_col().find({"job_id": job_id, "_id": {"$nin": seen}}).to_list(length=500)
            for r in new_runs:
                seen.append(r["_id"])
                yield sse("run", serialize(r))

            progress = {k: job.get(k) for k in ("status", "total", "completed", "passed", "failed", "error")}
            if progress != last_progress:
                last_progress = progress
                yield sse("progress", progress)

            if job.get("status") in TERMINAL:
                yield sse("done", progress)
                return

            ticks += 1
            if ticks % 20 == 0:
                yield ": keep-alive\n\n"
            await asyncio.sleep(0.75)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Results ───────────────────────────────────────────────

@router.get("/agent/{agent_id}")
async def get_runs_for_agent(
    agent_id: str,
    version: str | None = None,
    job_id: str | None = None,
    failed_only: bool = False,
    include_trace: bool = True,
    limit: int = 500,
):
    query: dict = {"agent_id": agent_id}
    if version:
        query["agent_version"] = version
    if job_id:
        query["job_id"] = job_id
    if failed_only:
        query["passed"] = False
    projection = None if include_trace else {"trace": 0}
    cursor = runs_col().find(query, projection).sort("created_at", -1).limit(max(1, min(limit, 2000)))
    docs = await cursor.to_list(length=None)
    return [serialize(d) for d in docs]


@router.delete("/agent/{agent_id}")
async def clear_runs(agent_id: str):
    runs = await runs_col().delete_many({"agent_id": agent_id})
    await reports_col().delete_many({"agent_id": agent_id, "type": "scorecard"})
    await jobs_col().delete_many({"agent_id": agent_id, "status": {"$in": list(TERMINAL)}})
    return {"deleted_runs": runs.deleted_count}


@router.get("/variance/{agent_id}")
async def get_variance(agent_id: str, version: str | None = None):
    """Per-scenario pass rate and flakiness across all stored trials."""
    query: dict = {"agent_id": agent_id}
    if version:
        query["agent_version"] = version
    docs = await runs_col().find(query, {"trace": 0}).to_list(length=5000)
    stats = _aggregate_variance(docs, await _scenario_titles(agent_id))
    return {
        "agent_id": agent_id,
        "version": version,
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
    docs = await runs_col().find(
        {"agent_id": agent_id},
        {"scenario_id": 1, "agent_version": 1, "created_at": 1, "passed": 1},
    ).to_list(length=10000)
    if not docs:
        raise HTTPException(status_code=400, detail="No runs found for this agent.")

    # Order versions by most-recent run time.
    ver_time: dict[str, float] = {}
    for d in docs:
        v = d.get("agent_version") or "unknown"
        t = d.get("created_at")
        ts = t.timestamp() if isinstance(t, datetime) else 0.0
        ver_time[v] = max(ver_time.get(v, 0.0), ts)
    versions_sorted = sorted(ver_time, key=lambda v: ver_time[v])

    head_version = head_version or (versions_sorted[-1] if versions_sorted else "unknown")
    if base_version is None:
        older = [v for v in versions_sorted if v != head_version]
        base_version = older[-1] if older else head_version

    empty_summary = {"regressed": 0, "improved": 0, "unchanged": 0, "new": 0, "removed": 0}
    if base_version == head_version:
        return {
            "agent_id": agent_id, "base_version": base_version, "head_version": head_version,
            "available_versions": versions_sorted,
            "note": "Need runs from two different agent versions to compare. "
                    "Bump the agent version and re-run.",
            "summary": empty_summary, "base_pass_rate": None, "head_pass_rate": None,
            "regressed": [], "improved": [], "unchanged": [], "new": [], "removed": [],
        }

    base_runs = [d for d in docs if (d.get("agent_version") or "unknown") == base_version]
    head_runs = [d for d in docs if (d.get("agent_version") or "unknown") == head_version]
    base_out = _majority_by_scenario(base_runs)
    head_out = _majority_by_scenario(head_runs)

    title = await _scenario_titles(agent_id)

    regressed, improved, unchanged, new_, removed = [], [], [], [], []
    for sid in sorted(set(base_out) | set(head_out)):
        entry = {"scenario_id": sid, "title": title.get(sid, sid)}
        b, h = base_out.get(sid), head_out.get(sid)
        if b is None:
            new_.append({**entry, "passed": h})
        elif h is None:
            removed.append(entry)
        elif b and not h:
            regressed.append(entry)
        elif (not b) and h:
            improved.append(entry)
        else:
            unchanged.append({**entry, "passed": h})

    def rate(rs):
        return round(sum(1 for r in rs if r.get("passed")) / len(rs), 4) if rs else None

    return {
        "agent_id": agent_id,
        "base_version": base_version,
        "head_version": head_version,
        "available_versions": versions_sorted,
        "base_pass_rate": rate(base_runs),
        "head_pass_rate": rate(head_runs),
        "summary": {
            "regressed": len(regressed), "improved": len(improved),
            "unchanged": len(unchanged), "new": len(new_), "removed": len(removed),
        },
        "regressed": regressed, "improved": improved,
        "unchanged": unchanged, "new": new_, "removed": removed,
    }


@router.get("/{run_id}")
async def get_run(run_id: str):
    doc = await runs_col().find_one({"_id": parse_object_id(run_id, "run id")})
    if not doc:
        raise HTTPException(status_code=404, detail="Run not found")
    return serialize(doc)
