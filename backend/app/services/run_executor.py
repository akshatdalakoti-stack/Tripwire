"""
services/run_executor.py — Executes (scenario x trial) runs and persists them.

Shared by the synchronous POST /runs/start endpoint and background jobs.
"""

import asyncio
from typing import Awaitable, Callable

from app.config import settings
from app.database import runs_col, scenarios_col
from app.models.agent import AgentConfig
from app.models.run import FailureMode, RunStatus
from app.models.scenario import Scenario
from app.services.failure_classifier import classify_failure
from app.services.sandbox import run_scenario
from app.utils.ids import parse_object_id

OnResult = Callable[[dict], Awaitable[None]]


async def load_scenarios(agent_id: str, scenario_ids: list[str] | None = None) -> list[dict]:
    query: dict = {"agent_id": agent_id}
    if scenario_ids:
        query["_id"] = {"$in": [parse_object_id(s, "scenario id") for s in scenario_ids]}
    return await scenarios_col().find(query).to_list(length=500)


async def execute_one(
    agent: AgentConfig,
    agent_id: str,
    sdoc: dict,
    trial_idx: int,
    job_id: str | None = None,
) -> dict:
    scenario = Scenario(**{k: v for k, v in sdoc.items() if k != "_id"})
    scenario_id = str(sdoc["_id"])

    run_result = await run_scenario(agent, scenario)
    run_result.scenario_id = scenario_id
    run_result.agent_id = agent_id

    if run_result.status == RunStatus.FAILED:
        # Infrastructure error (rate limit, network) — not the agent's fault,
        # and classifying it would just burn another LLM call.
        classification = {
            "failure_mode": FailureMode.UNKNOWN, "confidence": 1.0,
            "reasoning": run_result.failure_reason or "Run errored", "key_evidence": "", "source": "error",
        }
    else:
        classification = await classify_failure(run_result, scenario.description, scenario.expected_outcome)

    run_result.failure_mode = classification["failure_mode"]
    run_result.failure_reason = classification["reasoning"] or run_result.failure_reason
    # The final verdict decides pass/fail — a run the LLM labels GOAL_DRIFT is a failure.
    run_result.passed = run_result.failure_mode == FailureMode.PASS

    data = run_result.model_dump(mode="python")
    data.update({
        "scenario_type": scenario.scenario_type.value,
        "scenario_title": scenario.title,
        "pressure_level": scenario.pressure_level,
        "classifier_confidence": classification["confidence"],
        "classifier_source": classification.get("source", "llm"),
        "key_evidence": classification["key_evidence"],
        "trial_idx": trial_idx,
        "agent_version": agent.version,
        "job_id": job_id,
    })
    data["failure_mode"] = run_result.failure_mode.value
    data["status"] = run_result.status.value
    insert = await runs_col().insert_one(data)
    data["id"] = str(insert.inserted_id)
    data.pop("_id", None)
    return data


async def execute_batch(
    agent: AgentConfig,
    agent_id: str,
    scenario_docs: list[dict],
    trials: int,
    job_id: str | None = None,
    on_result: OnResult | None = None,
) -> list[dict]:
    """Run every scenario `trials` times, at most MAX_CONCURRENT_RUNS at once."""
    sem = asyncio.Semaphore(max(1, settings.MAX_CONCURRENT_RUNS))

    async def _bounded(sdoc: dict, t: int) -> dict:
        async with sem:
            data = await execute_one(agent, agent_id, sdoc, t, job_id)
        if on_result:
            await on_result(data)
        return data

    tasks = [_bounded(sdoc, t) for sdoc in scenario_docs for t in range(trials)]
    return list(await asyncio.gather(*tasks))
