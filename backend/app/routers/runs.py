"""
routers/runs.py — Sandbox execution + results
POST   /api/runs/start/{agent_id}    → Run all scenarios in sandbox (auto-classifies)
GET    /api/runs/{run_id}            → Get a single run result
GET    /api/runs/agent/{agent_id}    → Get all runs for an agent
"""

from fastapi import APIRouter, HTTPException
from bson import ObjectId
from app.database import runs_col, scenarios_col, agents_col
from app.models.agent import AgentConfig
from app.models.scenario import Scenario
from app.services.sandbox import run_scenario
from app.services.failure_classifier import classify_failure

router = APIRouter()


def serialize(doc: dict) -> dict:
    doc["id"] = str(doc.pop("_id"))
    return doc


@router.post("/start/{agent_id}")
async def start_run(agent_id: str):
    # Fetch agent
    agent_doc = await agents_col().find_one({"_id": ObjectId(agent_id)})
    if not agent_doc:
        raise HTTPException(status_code=404, detail="Agent not found")

    agent = AgentConfig(**{k: v for k, v in agent_doc.items() if k != "_id"})

    # Fetch scenarios for this agent
    scenario_docs = await scenarios_col().find({"agent_id": agent_id}).to_list(length=100)
    if not scenario_docs:
        raise HTTPException(status_code=400, detail="No scenarios found. Generate scenarios first.")

    results = []

    for sdoc in scenario_docs:
        scenario = Scenario(**{k: v for k, v in sdoc.items() if k != "_id"})
        scenario_id = str(sdoc["_id"])

        # Run scenario in sandbox
        run_result = await run_scenario(agent, scenario)
        run_result.scenario_id = scenario_id
        run_result.agent_id = agent_id

        # Auto-classify failure (Gemini reads the trace)
        classification = await classify_failure(run_result, scenario.description)
        run_result.failure_mode = classification["failure_mode"]
        run_result.failure_reason = classification["reasoning"]

        # Persist run
        data = run_result.model_dump()
        data["scenario_type"] = scenario.scenario_type.value
        data["classifier_confidence"] = classification["confidence"]
        data["key_evidence"] = classification["key_evidence"]
        insert = await runs_col().insert_one(data)
        data["id"] = str(insert.inserted_id)
        data.pop("_id", None)
        results.append(data)

    return {
        "agent_id": agent_id,
        "total_runs": len(results),
        "passed": sum(1 for r in results if r.get("passed")),
        "failed": sum(1 for r in results if not r.get("passed")),
        "runs": results,
    }


@router.get("/agent/{agent_id}")
async def get_runs_for_agent(agent_id: str):
    cursor = runs_col().find({"agent_id": agent_id})
    docs = await cursor.to_list(length=500)
    return [serialize(d) for d in docs]


@router.get("/{run_id}")
async def get_run(run_id: str):
    doc = await runs_col().find_one({"_id": ObjectId(run_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Run not found")
    return serialize(doc)
