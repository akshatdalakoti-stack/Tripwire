"""
utils/loaders.py — Shared "fetch or 404" helpers for routers.
"""

from fastapi import HTTPException

from app.database import agents_col
from app.models.agent import AgentConfig
from app.utils.ids import parse_object_id


async def load_agent(agent_id: str) -> tuple[AgentConfig, dict]:
    """Return (validated AgentConfig, raw Mongo doc) or raise 404."""
    doc = await agents_col().find_one({"_id": parse_object_id(agent_id, "agent id")})
    if not doc:
        raise HTTPException(status_code=404, detail="Agent not found")
    agent = AgentConfig(**{k: v for k, v in doc.items() if k != "_id"})
    return agent, doc
