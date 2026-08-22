"""
routers/guardrails.py — Guardrail probe execution + results
POST   /api/guardrails/run/{agent_id}   → Run all safety probes
GET    /api/guardrails/agent/{agent_id} → Get latest guardrail results
"""

from fastapi import APIRouter, HTTPException
from bson import ObjectId
from datetime import datetime, timezone
from app.database import agents_col, reports_col
from app.models.agent import AgentConfig
from app.services.guardrail_tester import run_guardrail_probes, compute_guardrail_pass_rate

router = APIRouter()


@router.post("/run/{agent_id}")
async def run_guardrails(agent_id: str):
    agent_doc = await agents_col().find_one({"_id": ObjectId(agent_id)})
    if not agent_doc:
        raise HTTPException(status_code=404, detail="Agent not found")

    agent = AgentConfig(**{k: v for k, v in agent_doc.items() if k != "_id"})
    results = await run_guardrail_probes(agent)
    pass_rate = compute_guardrail_pass_rate(results)

    # Persist as a lightweight guardrail snapshot
    snapshot = {
        "agent_id": agent_id,
        "type": "guardrail_snapshot",
        "results": [r.model_dump() for r in results],
        "pass_rate": pass_rate,
        "total_probes": len(results),
        "passed_probes": sum(1 for r in results if r.refused),
        "generated_at": datetime.now(timezone.utc),
    }
    await reports_col().insert_one(snapshot)

    return {
        "agent_id": agent_id,
        "total_probes": len(results),
        "passed": sum(1 for r in results if r.refused),
        "pass_rate": pass_rate,
        "results": [r.model_dump() for r in results],
    }


@router.get("/agent/{agent_id}")
async def get_guardrail_results(agent_id: str):
    doc = await reports_col().find_one(
        {"agent_id": agent_id, "type": "guardrail_snapshot"},
        sort=[("generated_at", -1)],
    )
    if not doc:
        return {"agent_id": agent_id, "results": [], "pass_rate": 0.0}

    doc["id"] = str(doc.pop("_id"))
    return doc
