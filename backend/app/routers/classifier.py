"""
routers/classifier.py — Failure classification results
GET    /api/classify/agent/{agent_id}  → Get all classified failures for an agent

Note: Classification happens automatically inside /api/runs/start.
This router only exposes pre-stored results for the frontend report view.
"""

from fastapi import APIRouter
from app.database import runs_col

router = APIRouter()


def serialize(doc: dict) -> dict:
    doc["id"] = str(doc.pop("_id"))
    return doc


@router.get("/agent/{agent_id}")
async def get_classifications(agent_id: str):
    """Return failure classifications for all runs of an agent."""
    cursor = runs_col().find(
        {"agent_id": agent_id, "passed": False},
        {
            "_id": 1,
            "scenario_id": 1,
            "failure_mode": 1,
            "failure_reason": 1,
            "classifier_confidence": 1,
            "key_evidence": 1,
            "scenario_type": 1,
            "duration_ms": 1,
            "created_at": 1,
        }
    )
    docs = await cursor.to_list(length=500)
    return [serialize(d) for d in docs]
