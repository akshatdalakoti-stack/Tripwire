"""
utils/trace_logger.py — Utilities for building execution traces.
Used by the sandbox to record each agent step cleanly.
"""

from datetime import datetime, timezone
from app.models.run import TraceStep


def make_tool_step(
    step_number: int,
    tool_name: str,
    tool_input: dict,
    tool_output,
    flagged: bool = False,
    flag_reason: str | None = None,
) -> TraceStep:
    return TraceStep(
        step_number=step_number,
        action="tool_call",
        tool_name=tool_name,
        tool_input=tool_input,
        tool_output=tool_output,
        flagged=flagged,
        flag_reason=flag_reason,
        timestamp=datetime.now(timezone.utc),
    )


def make_llm_step(step_number: int, response: str) -> TraceStep:
    return TraceStep(
        step_number=step_number,
        action="llm_response",
        llm_response=response,
        timestamp=datetime.now(timezone.utc),
    )


def make_error_step(step_number: int, error_msg: str) -> TraceStep:
    return TraceStep(
        step_number=step_number,
        action="error",
        llm_response=error_msg,
        flagged=True,
        flag_reason="execution_error",
        timestamp=datetime.now(timezone.utc),
    )


def detect_tool_loop(trace: list[TraceStep], threshold: int = 4) -> bool:
    """Returns True if any single tool was called >= threshold times."""
    tool_counts: dict[str, int] = {}
    for step in trace:
        if step.action == "tool_call" and step.tool_name:
            tool_counts[step.tool_name] = tool_counts.get(step.tool_name, 0) + 1
            if tool_counts[step.tool_name] >= threshold:
                return True
    return False
