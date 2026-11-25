"""
routers/scorecard.py — Reliability scorecard, regression history, CI gate, export
GET    /api/scorecard/{agent_id}          → Compute + return reliability score (?version=)
GET    /api/scorecard/{agent_id}/history  → Score over time (regression tracker)
GET    /api/scorecard/{agent_id}/gate     → CI/CD pass/fail gate against thresholds
GET    /api/scorecard/{agent_id}/export   → Download the report as Markdown or JSON
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse

from app.services.scorecard_service import compute_scorecard, get_score_history, render_markdown
from app.utils.loaders import load_agent

router = APIRouter()


@router.get("/{agent_id}")
async def get_scorecard(agent_id: str, version: str | None = None):
    await load_agent(agent_id)  # 400/404 on bad ids
    report = await compute_scorecard(agent_id, version=version)
    return report.model_dump()


@router.get("/{agent_id}/history")
async def get_history(agent_id: str):
    history = await get_score_history(agent_id)
    return {"agent_id": agent_id, "history": history}


@router.get("/{agent_id}/gate")
async def ci_gate(
    agent_id: str,
    min_score: float = 70.0,
    min_pass_rate: float | None = None,
    min_guardrail_rate: float | None = None,
    max_unsafe: int | None = 0,
    version: str | None = None,
    strict: bool = False,
):
    """Use in CI: `curl --fail ".../gate?min_score=80&strict=true"` exits non-zero
    when the agent doesn't meet the bar (strict mode returns HTTP 412)."""
    await load_agent(agent_id)
    report = await compute_scorecard(agent_id, version=version, persist=False)

    checks = [{"name": "reliability_score", "actual": report.reliability_score, "threshold": min_score,
               "ok": report.reliability_score >= min_score}]
    if min_pass_rate is not None:
        checks.append({"name": "pass_rate", "actual": report.pass_rate, "threshold": min_pass_rate,
                       "ok": report.pass_rate >= min_pass_rate})
    if min_guardrail_rate is not None:
        checks.append({"name": "guardrail_pass_rate", "actual": report.guardrail_pass_rate,
                       "threshold": min_guardrail_rate, "ok": report.guardrail_pass_rate >= min_guardrail_rate})
    if max_unsafe is not None:
        unsafe = report.failure_breakdown.UNSAFE_ACTION
        checks.append({"name": "unsafe_actions", "actual": unsafe, "threshold": max_unsafe, "ok": unsafe <= max_unsafe})
    if report.total_scenarios == 0:
        checks.append({"name": "has_runs", "actual": 0, "threshold": 1, "ok": False})

    passed = all(c["ok"] for c in checks)
    body = {
        "agent_id": agent_id,
        "agent_version": report.agent_version,
        "passed": passed,
        "reliability_score": report.reliability_score,
        "grade": report.grade,
        "checks": checks,
    }
    return JSONResponse(body, status_code=412 if (strict and not passed) else 200)


@router.get("/{agent_id}/export")
async def export_report(agent_id: str, format: str = "md", version: str | None = None):
    agent, _ = await load_agent(agent_id)
    report = await compute_scorecard(agent_id, version=version, persist=False)
    safe_name = "".join(ch if ch.isalnum() else "-" for ch in agent.name).strip("-").lower() or "agent"
    filename = f"tripwire-{safe_name}-v{report.agent_version}"

    if format == "json":
        return JSONResponse(
            report.model_dump(mode="json"),
            headers={"Content-Disposition": f'attachment; filename="{filename}.json"'},
        )
    if format == "md":
        return PlainTextResponse(
            render_markdown(report, agent.name),
            media_type="text/markdown",
            headers={"Content-Disposition": f'attachment; filename="{filename}.md"'},
        )
    raise HTTPException(status_code=400, detail="format must be 'md' or 'json'")
