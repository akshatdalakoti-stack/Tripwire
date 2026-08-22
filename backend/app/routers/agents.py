"""
routers/agents.py — Agent CRUD
POST   /api/agents          → Create agent
GET    /api/agents          → List all agents
GET    /api/agents/{id}     → Get single agent
"""

from fastapi import APIRouter, HTTPException
from bson import ObjectId
from app.models.agent import AgentConfig
from app.database import agents_col

router = APIRouter()


def serialize(doc: dict) -> dict:
    doc["id"] = str(doc.pop("_id"))
    return doc


@router.post("", status_code=201)
async def create_agent(agent: AgentConfig):
    data = agent.model_dump()
    result = await agents_col().insert_one(data)
    data["id"] = str(result.inserted_id)
    return data


@router.get("")
async def list_agents():
    cursor = agents_col().find()
    agents = await cursor.to_list(length=100)
    return [serialize(a) for a in agents]


@router.get("/{agent_id}")
async def get_agent(agent_id: str):
    doc = await agents_col().find_one({"_id": ObjectId(agent_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Agent not found")
    return serialize(doc)


@router.delete("/{agent_id}", status_code=204)
async def delete_agent(agent_id: str):
    result = await agents_col().delete_one({"_id": ObjectId(agent_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Agent not found")
