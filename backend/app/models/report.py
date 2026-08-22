"""
models/report.py — Reliability report schema.
Aggregates all runs for an agent into a scored report.
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, timezone


class FailureBreakdown(BaseModel):
    PASS: int = 0
    TOOL_LOOP: int = 0
    HALLUCINATED_CONFIDENCE: int = 0
    UNSAFE_ACTION: int = 0
    GOAL_DRIFT: int = 0
    TIMEOUT: int = 0
    UNKNOWN: int = 0


class GuardrailResult(BaseModel):
    probe: str = Field(..., description="The adversarial probe text")
    refused: bool = Field(..., description="True if the agent correctly refused")
    response_snippet: str = Field(default="")


class ReliabilityReport(BaseModel):
    agent_id: str
    agent_version: str
    total_scenarios: int
    passed: int
    failed: int
    pass_rate: float                         # 0.0 – 1.0
    reliability_score: float                 # 0 – 100
    failure_breakdown: FailureBreakdown
    guardrail_results: list[GuardrailResult] = []
    guardrail_pass_rate: float = 0.0
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ReliabilityReportInDB(ReliabilityReport):
    id: str = Field(..., alias="_id")

    class Config:
        populate_by_name = True
