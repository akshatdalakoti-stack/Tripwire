"""
routers/scenarios.py — Scenario generation + retrieval
POST   /api/scenarios/generate      → Generate scenarios for an agent
GET    /api/scenarios/{agent_id}    → Get all scenarios for an agent
"""

from fastapi import APIRouter, HTTPException
from bson import ObjectId
from app.database import scenarios_col, agents_col
from app.models.agent import AgentConfig
from app.services.scenario_engine import generate_scenarios

router = APIRouter()


def serialize(doc: dict) -> dict:
    doc["id"] = str(doc.pop("_id"))
    return doc


@router.post("/generate")
async def generate(agent_id: str, count: int = 10):
    # Fetch agent
    agent_doc = await agents_col().find_one({"_id": ObjectId(agent_id)})
    if not agent_doc:
        raise HTTPException(status_code=404, detail="Agent not found")

    agent = AgentConfig(**{k: v for k, v in agent_doc.items() if k != "_id"})
    scenarios = await generate_scenarios(agent, count=count)

    # Persist each scenario
    saved = []
    for s in scenarios:
        data = s.model_dump()
        data["agent_id"] = agent_id
        result = await scenarios_col().insert_one(data)
        data["id"] = str(result.inserted_id)
        data.pop("_id", None)  # Remove ObjectId to prevent JSON serialization 500 errors
        saved.append(data)

    return {"generated": len(saved), "scenarios": saved}


@router.get("/{agent_id}")
async def get_scenarios(agent_id: str):
    cursor = scenarios_col().find({"agent_id": agent_id})
    docs = await cursor.to_list(length=200)
    return [serialize(d) for d in docs]
