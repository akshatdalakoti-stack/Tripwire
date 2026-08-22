"""
routers/classifier.py — Failure classification
POST   /api/classify/{run_id}          → Re-classify a specific run
GET    /api/classify/agent/{agent_id}  → Get all failure classifications for an agent
"""

from fastapi import APIRouter, HTTPException
from bson import ObjectId
from app.database import runs_col
from app.models.run import RunResult
from app.services.failure_classifier import classify_failure

router = APIRouter()


def serialize(doc: dict) -> dict:
    doc["id"] = str(doc.pop("_id"))
    return doc


@router.post("/{run_id}")
async def classify_run(run_id: str):
    doc = await runs_col().find_one({"_id": ObjectId(run_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Run not found")

    run = RunResult(**{k: v for k, v in doc.items() if k != "_id"})
    classification = await classify_failure(run)

    await runs_col().update_one(
        {"_id": ObjectId(run_id)},
        {"$set": {
            "failure_mode": classification["failure_mode"].value,
            "failure_reason": classification["reasoning"],
            "classifier_confidence": classification["confidence"],
            "key_evidence": classification["key_evidence"],
        }}
    )
    return classification


@router.get("/agent/{agent_id}")
async def get_classifications(agent_id: str):
    cursor = runs_col().find(
        {"agent_id": agent_id, "passed": False},
        {"_id": 1, "scenario_id": 1, "failure_mode": 1, "failure_reason": 1,
         "classifier_confidence": 1, "key_evidence": 1, "scenario_type": 1,
         "duration_ms": 1, "created_at": 1}
    )
    docs = await cursor.to_list(length=500)
    return [serialize(d) for d in docs]
