"""
routers/scenarios.py — Scenario generation + management
POST   /api/scenarios/generate           → Generate scenarios for an agent (LLM)
POST   /api/scenarios                    → Add a hand-written scenario
GET    /api/scenarios/{agent_id}         → Get all scenarios for an agent
DELETE /api/scenarios/item/{scenario_id} → Delete one scenario
DELETE /api/scenarios/agent/{agent_id}   → Delete all scenarios for an agent
"""

from fastapi import APIRouter, HTTPException
from app.config import settings
from app.database import scenarios_col
from app.models.scenario import Scenario, ScenarioCreate, ScenarioType
from app.services.scenario_engine import generate_scenarios
from app.utils.ids import parse_object_id, serialize
from app.utils.loaders import load_agent

router = APIRouter()


@router.post("/generate")
async def generate(agent_id: str, count: int = 10, focus: str | None = None):
    count = max(1, min(count, settings.MAX_SCENARIOS_PER_GENERATION))
    agent, _ = await load_agent(agent_id)

    existing = await scenarios_col().find({"agent_id": agent_id}, {"title": 1}).to_list(length=500)
    scenarios = await generate_scenarios(
        agent, count=count, focus=focus, existing_titles=[e.get("title", "") for e in existing],
    )
    if not scenarios:
        raise HTTPException(status_code=502, detail="The model returned no usable scenarios. Try again.")

    docs = []
    for s in scenarios:
        data = s.model_dump()
        data["agent_id"] = agent_id
        data["source"] = "generated"
        docs.append(data)

    # One round trip instead of one insert per scenario.
    result = await scenarios_col().insert_many(docs)
    for data, oid in zip(docs, result.inserted_ids):
        data.pop("_id", None)
        data["id"] = str(oid)

    return {"generated": len(docs), "scenarios": docs}


@router.post("", status_code=201)
async def create_scenario(body: ScenarioCreate):
    agent, _ = await load_agent(body.agent_id)
    tool_names = {t.name for t in agent.tools}
    unknown = [k for k in body.injected_tool_outputs if k not in tool_names]
    if unknown:
        raise HTTPException(status_code=400, detail=f"Injected outputs target unknown tools: {', '.join(unknown)}")

    scenario = Scenario(
        agent_id=body.agent_id,
        title=body.title,
        description=body.description,
        scenario_type=body.scenario_type,
        is_adversarial=body.scenario_type != ScenarioType.REALISTIC or body.pressure_level >= 2,
        expected_outcome=body.expected_outcome,
        pressure_level=body.pressure_level,
        injected_tool_outputs=body.injected_tool_outputs,
    )
    data = scenario.model_dump()
    data["source"] = "manual"
    result = await scenarios_col().insert_one(data)
    data.pop("_id", None)
    data["id"] = str(result.inserted_id)
    return data


@router.get("/{agent_id}")
async def get_scenarios(agent_id: str):
    cursor = scenarios_col().find({"agent_id": agent_id}).sort("created_at", 1)
    docs = await cursor.to_list(length=500)
    return [serialize(d) for d in docs]


@router.delete("/item/{scenario_id}", status_code=204)
async def delete_scenario(scenario_id: str):
    result = await scenarios_col().delete_one({"_id": parse_object_id(scenario_id, "scenario id")})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Scenario not found")


@router.delete("/agent/{agent_id}")
async def delete_all_scenarios(agent_id: str):
    result = await scenarios_col().delete_many({"agent_id": agent_id})
    return {"deleted": result.deleted_count}
