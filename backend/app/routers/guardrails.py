"""
routers/guardrails.py — Guardrail probe execution + results
GET    /api/guardrails/probes/{agent_id} → Preview the probes that would run
POST   /api/guardrails/run/{agent_id}    → Run all safety probes (+ optional custom probes)
GET    /api/guardrails/agent/{agent_id}  → Get latest guardrail results
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Body
from pydantic import BaseModel

from app.database import reports_col
from app.services.guardrail_tester import (
    build_probes, compute_guardrail_pass_rate, guardrail_by_category, run_guardrail_probes,
)
from app.utils.loaders import load_agent
from app.utils.ids import serialize

router = APIRouter()


class GuardrailRequest(BaseModel):
    extra_probes: list[str] = []
    use_llm_judge: bool | None = None


@router.get("/probes/{agent_id}")
async def preview_probes(agent_id: str):
    agent, _ = await load_agent(agent_id)
    return [{"category": c, "probe": p} for c, p in build_probes(agent)]


@router.post("/run/{agent_id}")
async def run_guardrails(agent_id: str, req: GuardrailRequest | None = Body(default=None)):
    agent, _ = await load_agent(agent_id)
    req = req or GuardrailRequest()
    results = await run_guardrail_probes(agent, req.extra_probes, req.use_llm_judge)
    pass_rate = compute_guardrail_pass_rate(results)
    passed = sum(1 for r in results if r.refused)
    dumped = [r.model_dump() for r in results]
    categories = guardrail_by_category(results)

    # Persist as a lightweight guardrail snapshot
    snapshot = {
        "agent_id": agent_id,
        "agent_version": agent.version,
        "type": "guardrail_snapshot",
        "results": dumped,
        "pass_rate": pass_rate,
        "by_category": categories,
        "total_probes": len(results),
        "passed_probes": passed,
        "generated_at": datetime.now(timezone.utc),
    }
    await reports_col().insert_one(snapshot)

    return {
        "agent_id": agent_id,
        "agent_version": agent.version,
        "total_probes": len(results),
        "passed": passed,
        "pass_rate": pass_rate,
        "by_category": categories,
        "results": dumped,
    }


@router.get("/agent/{agent_id}")
async def get_guardrail_results(agent_id: str):
    doc = await reports_col().find_one(
        {"agent_id": agent_id, "type": "guardrail_snapshot"},
        sort=[("generated_at", -1)],
    )
    if not doc:
        return {"agent_id": agent_id, "results": [], "pass_rate": 0.0, "by_category": []}
    return serialize(doc)
