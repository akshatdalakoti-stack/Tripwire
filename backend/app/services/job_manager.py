"""
services/job_manager.py — Background test-run jobs with live progress.

A job is persisted in the `jobs` collection and its runs are tagged with
`job_id`, so progress can be read (and streamed over SSE) from any worker.
The asyncio task itself lives in the worker that started it; cancelling only
works there, which is fine for a single-process deployment.
"""

import asyncio
from datetime import datetime, timezone

from bson import ObjectId

from app.database import jobs_col
from app.models.agent import AgentConfig
from app.services.run_executor import execute_batch
from app.services.scorecard_service import compute_scorecard, is_infra_error

TERMINAL = {"completed", "failed", "cancelled", "interrupted"}

_tasks: dict[str, asyncio.Task] = {}


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def mark_interrupted_jobs() -> None:
    """On startup: jobs left 'running' by a previous process will never finish."""
    await jobs_col().update_many(
        {"status": {"$in": ["queued", "running"]}},
        {"$set": {"status": "interrupted", "finished_at": _now(),
                  "error": "Server restarted while this job was running."}},
    )


async def start_job(
    agent: AgentConfig,
    agent_id: str,
    scenario_docs: list[dict],
    trials: int,
) -> dict:
    job = {
        "agent_id": agent_id,
        "agent_version": agent.version,
        "status": "running",
        "trials": trials,
        "scenario_count": len(scenario_docs),
        "total": len(scenario_docs) * trials,
        "completed": 0,
        "passed": 0,
        "failed": 0,
        "errored": 0,
        "error": None,
        "created_at": _now(),
        "finished_at": None,
    }
    res = await jobs_col().insert_one(job)
    job_id = str(res.inserted_id)

    async def on_result(run: dict) -> None:
        bucket = "errored" if is_infra_error(run) else ("passed" if run.get("passed") else "failed")
        await jobs_col().update_one(
            {"_id": res.inserted_id},
            {"$inc": {"completed": 1, bucket: 1}},
        )

    async def runner() -> None:
        try:
            await execute_batch(agent, agent_id, scenario_docs, trials, job_id=job_id, on_result=on_result)
            await jobs_col().update_one({"_id": res.inserted_id},
                                        {"$set": {"status": "completed", "finished_at": _now()}})
            try:
                # Snapshot the score so the regression history gains a point per job.
                await compute_scorecard(agent_id)
            except Exception:
                pass
        except asyncio.CancelledError:
            await jobs_col().update_one({"_id": res.inserted_id},
                                        {"$set": {"status": "cancelled", "finished_at": _now()}})
        except Exception as e:
            await jobs_col().update_one({"_id": res.inserted_id},
                                        {"$set": {"status": "failed", "finished_at": _now(),
                                                  "error": str(getattr(e, "detail", e))}})
        finally:
            _tasks.pop(job_id, None)

    _tasks[job_id] = asyncio.create_task(runner())
    job["id"] = job_id
    job.pop("_id", None)
    return job


async def cancel_job(job_id: str) -> bool:
    task = _tasks.get(job_id)
    if task and not task.done():
        task.cancel()
        return True
    # Not running in this worker — mark it so the UI stops waiting.
    result = await jobs_col().update_one(
        {"_id": ObjectId(job_id), "status": {"$in": ["queued", "running"]}},
        {"$set": {"status": "cancelled", "finished_at": _now()}},
    )
    return result.modified_count > 0
