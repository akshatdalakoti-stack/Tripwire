"""
routers/classifier.py — Failure classification
POST   /api/classify/{run_id}          → Re-classify a specific run (always uses the LLM)
GET    /api/classify/agent/{agent_id}  → Get all failure classifications for an agent
"""

from fastapi import APIRouter, HTTPException
from app.database import runs_col, scenarios_col
from app.models.run import RunResult, FailureMode
from app.services.failure_classifier import classify_failure
from app.utils.ids import parse_object_id, serialize

router = APIRouter()


@router.post("/{run_id}")
async def classify_run(run_id: str):
    oid = parse_object_id(run_id, "run id")
    doc = await runs_col().find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Run not found")

    run = RunResult(**{k: v for k, v in doc.items() if k != "_id"})
    description, expected = "", ""
    try:
        scen = await scenarios_col().find_one({"_id": parse_object_id(run.scenario_id)})
        if scen:
            description, expected = scen.get("description", ""), scen.get("expected_outcome", "")
    except HTTPException:
        pass  # legacy runs reference scenarios by name, not ObjectId

    classification = await classify_failure(run, description, expected, force_llm=True)
    mode = classification["failure_mode"]

    await runs_col().update_one(
        {"_id": oid},
        {"$set": {
            "failure_mode": mode.value,
            "passed": mode == FailureMode.PASS,
            "failure_reason": classification["reasoning"],
            "classifier_confidence": classification["confidence"],
            "classifier_source": classification["source"],
            "key_evidence": classification["key_evidence"],
        }}
    )
    return {**classification, "failure_mode": mode.value}


@router.get("/agent/{agent_id}")
async def get_classifications(agent_id: str):
    cursor = runs_col().find(
        {"agent_id": agent_id, "passed": False},
        {"_id": 1, "scenario_id": 1, "scenario_title": 1, "failure_mode": 1, "failure_reason": 1,
         "classifier_confidence": 1, "classifier_source": 1, "key_evidence": 1, "scenario_type": 1,
         "pressure_level": 1, "agent_version": 1, "duration_ms": 1, "created_at": 1}
    ).sort("created_at", -1)
    docs = await cursor.to_list(length=500)
    return [serialize(d) for d in docs]
