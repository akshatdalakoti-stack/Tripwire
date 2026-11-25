"""
models/report.py — Reliability report schema.
Aggregates all runs for an agent into a scored report.
"""

from pydantic import BaseModel, Field, ConfigDict
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
    category: str = Field(default="general", description="Attack family, e.g. prompt_injection")
    verdict_source: str = Field(default="heuristic", description="'llm_judge' | 'heuristic' | 'tool_call' | 'error'")
    reason: str = Field(default="", description="Why the response was judged a refusal or not")


class BucketStat(BaseModel):
    """Pass rate for one slice of runs (a scenario type or a pressure level)."""
    key: str
    total: int = 0
    passed: int = 0
    pass_rate: float = 0.0


class ScoreComponents(BaseModel):
    base: float = 0.0
    guardrail: float = 0.0
    diversity: float = 0.0


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
    # ── v2 additions ──
    grade: str = "F"
    score_components: ScoreComponents = Field(default_factory=ScoreComponents)
    by_scenario_type: list[BucketStat] = []
    by_pressure_level: list[BucketStat] = []
    guardrail_by_category: list[BucketStat] = []
    unique_scenarios: int = 0
    flaky_scenarios: int = 0
    avg_duration_ms: Optional[float] = None
    avg_tool_calls: Optional[float] = None
    recommendations: list[str] = []
    versions_available: list[str] = []
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ReliabilityReportInDB(ReliabilityReport):
    id: str = Field(..., alias="_id")

    model_config = ConfigDict(populate_by_name=True)
