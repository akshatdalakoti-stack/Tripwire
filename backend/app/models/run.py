"""
models/run.py — Test run and execution trace schema.
Captures every step the agent took during a sandboxed run.
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Any
from datetime import datetime, timezone
from enum import Enum


class RunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class FailureMode(str, Enum):
    PASS = "PASS"
    TOOL_LOOP = "TOOL_LOOP"
    HALLUCINATED_CONFIDENCE = "HALLUCINATED_CONFIDENCE"
    UNSAFE_ACTION = "UNSAFE_ACTION"
    GOAL_DRIFT = "GOAL_DRIFT"
    TIMEOUT = "TIMEOUT"
    UNKNOWN = "UNKNOWN"


class TraceStep(BaseModel):
    step_number: int
    action: str = Field(..., description="'tool_call' | 'llm_response' | 'error'")
    tool_name: Optional[str] = None
    tool_input: Optional[dict] = None
    tool_output: Optional[Any] = None
    llm_response: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    flagged: bool = Field(default=False, description="True if this step looks suspicious")
    flag_reason: Optional[str] = None


class RunResult(BaseModel):
    scenario_id: str
    agent_id: str
    status: RunStatus = RunStatus.PENDING
    passed: bool = False
    failure_mode: FailureMode = FailureMode.UNKNOWN
    failure_reason: Optional[str] = None
    trace: list[TraceStep] = []
    total_tool_calls: int = 0
    duration_ms: Optional[int] = None
    final_answer: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RunResultInDB(RunResult):
    id: str = Field(..., alias="_id")

    model_config = ConfigDict(populate_by_name=True)
