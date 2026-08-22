"""
routers/scorecard.py — Reliability scorecard + regression history
GET    /api/scorecard/{agent_id}          → Compute + return reliability score
GET    /api/scorecard/{agent_id}/history  → Score over time (regression tracker)
"""

from fastapi import APIRouter, HTTPException
from bson import ObjectId
from app.database import agents_col, reports_col
from app.services.scorecard_service import compute_scorecard, get_score_history
from app.models.report import GuardrailResult

router = APIRouter()


@router.get("/{agent_id}")
async def get_scorecard(agent_id: str):
    agent_doc = await agents_col().find_one({"_id": ObjectId(agent_id)})
    if not agent_doc:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Pull latest guardrail results if they exist
    guardrail_snapshot = await reports_col().find_one(
        {"agent_id": agent_id, "type": "guardrail_snapshot"},
        sort=[("generated_at", -1)],
    )
    guardrail_results = None
    if guardrail_snapshot:
        guardrail_results = [
            GuardrailResult(**r) for r in guardrail_snapshot.get("results", [])
        ]

    report = await compute_scorecard(agent_id, guardrail_results)
    return report.model_dump()


@router.get("/{agent_id}/history")
async def get_history(agent_id: str):
    history = await get_score_history(agent_id)
    return {"agent_id": agent_id, "history": history}
