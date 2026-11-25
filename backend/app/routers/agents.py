"""
routers/agents.py — Agent CRUD
POST   /api/agents             → Create agent
GET    /api/agents             → List all agents (with latest score + run stats)
GET    /api/agents/{id}        → Get single agent
PUT    /api/agents/{id}        → Update agent (bump `version` to track regressions)
POST   /api/agents/{id}/clone  → Copy an agent (and optionally its scenarios)
DELETE /api/agents/{id}        → Delete agent and everything that belongs to it
"""

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from app.models.agent import AgentConfig, AgentUpdate
from app.database import agents_col, scenarios_col, runs_col, reports_col, jobs_col
from app.utils.ids import parse_object_id, serialize

router = APIRouter()


@router.post("", status_code=201)
async def create_agent(agent: AgentConfig):
    data = agent.model_dump()
    result = await agents_col().insert_one(data)
    data["id"] = str(result.inserted_id)
    data.pop("_id", None)
    return data


@router.get("")
async def list_agents():
    agents = await agents_col().find().sort("created_at", -1).to_list(length=200)

    # Three cheap aggregations instead of N+1 queries per agent.
    latest_scores = {
        d["_id"]: d async for d in reports_col().aggregate([
            {"$match": {"type": "scorecard"}},
            {"$sort": {"generated_at": -1}},
            {"$group": {"_id": "$agent_id", "score": {"$first": "$reliability_score"},
                        "grade": {"$first": "$grade"}, "version": {"$first": "$agent_version"},
                        "at": {"$first": "$generated_at"}}},
        ])
    }
    run_stats = {
        d["_id"]: d async for d in runs_col().aggregate([
            {"$group": {"_id": "$agent_id", "runs": {"$sum": 1},
                        "passed": {"$sum": {"$cond": ["$passed", 1, 0]}},
                        "last_run_at": {"$max": "$created_at"}}},
        ])
    }
    scenario_counts = {
        d["_id"]: d["n"] async for d in scenarios_col().aggregate([
            {"$group": {"_id": "$agent_id", "n": {"$sum": 1}}},
        ])
    }

    out = []
    for a in agents:
        a = serialize(a)
        score = latest_scores.get(a["id"])
        stats = run_stats.get(a["id"], {})
        a["latest_score"] = score["score"] if score else None
        a["latest_grade"] = score.get("grade") if score else None
        a["run_count"] = stats.get("runs", 0)
        a["pass_rate"] = round(stats["passed"] / stats["runs"], 4) if stats.get("runs") else None
        last = stats.get("last_run_at")
        a["last_run_at"] = last if isinstance(last, datetime) else None
        a["scenario_count"] = scenario_counts.get(a["id"], 0)
        out.append(a)
    return out


@router.get("/{agent_id}")
async def get_agent(agent_id: str):
    doc = await agents_col().find_one({"_id": parse_object_id(agent_id, "agent id")})
    if not doc:
        raise HTTPException(status_code=404, detail="Agent not found")
    return serialize(doc)


@router.put("/{agent_id}")
async def update_agent(agent_id: str, patch: AgentUpdate):
    oid = parse_object_id(agent_id, "agent id")
    changes = patch.model_dump(exclude_none=True)
    if not changes:
        raise HTTPException(status_code=400, detail="Nothing to update")
    changes["updated_at"] = datetime.now(timezone.utc)
    result = await agents_col().find_one_and_update({"_id": oid}, {"$set": changes}, return_document=True)
    if not result:
        raise HTTPException(status_code=404, detail="Agent not found")
    return serialize(result)


@router.post("/{agent_id}/clone", status_code=201)
async def clone_agent(agent_id: str, include_scenarios: bool = True):
    doc = await agents_col().find_one({"_id": parse_object_id(agent_id, "agent id")})
    if not doc:
        raise HTTPException(status_code=404, detail="Agent not found")
    doc.pop("_id")
    doc["name"] = f"{doc.get('name', 'Agent')} (copy)"
    doc["created_at"] = datetime.now(timezone.utc)
    doc.pop("updated_at", None)
    res = await agents_col().insert_one(doc)
    new_id = str(res.inserted_id)

    copied = 0
    if include_scenarios:
        scen = await scenarios_col().find({"agent_id": agent_id}).to_list(length=500)
        for s in scen:
            s.pop("_id")
            s["agent_id"] = new_id
        if scen:
            await scenarios_col().insert_many(scen)
            copied = len(scen)
    doc["id"] = new_id
    doc.pop("_id", None)
    doc["scenarios_copied"] = copied
    return doc


@router.delete("/{agent_id}", status_code=204)
async def delete_agent(agent_id: str):
    result = await agents_col().delete_one({"_id": parse_object_id(agent_id, "agent id")})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Agent not found")
    # Cascade — otherwise orphaned runs/reports pile up forever.
    await scenarios_col().delete_many({"agent_id": agent_id})
    await runs_col().delete_many({"agent_id": agent_id})
    await reports_col().delete_many({"agent_id": agent_id})
    await jobs_col().delete_many({"agent_id": agent_id})
