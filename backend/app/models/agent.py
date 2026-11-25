"""
models/agent.py — Agent configuration schema.
Defines what an AI agent looks like inside Tripwire.
"""

import re
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict
from typing import Optional
from datetime import datetime, timezone

TOOL_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class ToolDefinition(BaseModel):
    name: str = Field(..., description="Tool function name, e.g. 'send_email'")
    description: str = Field(..., description="What this tool does")
    is_destructive: bool = Field(
        default=False,
        description="True if this tool performs irreversible actions (delete, send, pay)"
    )
    canned_response: Optional[str] = Field(
        default=None,
        description="Optional fixed response to return when this mock tool is called"
    )

    @field_validator("name")
    @classmethod
    def valid_identifier(cls, v: str) -> str:
        v = v.strip()
        # The sandbox parses `TOOL_CALL: <name> | {...}`, so names must be identifiers.
        if not TOOL_NAME_RE.match(v):
            raise ValueError(f"Tool name '{v}' must be a code identifier (letters, digits, underscores)")
        return v


def _check_unique_tools(tools: list[ToolDefinition]) -> None:
    names = [t.name for t in tools]
    dupes = {n for n in names if names.count(n) > 1}
    if dupes:
        raise ValueError(f"Duplicate tool names: {', '.join(sorted(dupes))}")


class AgentConfig(BaseModel):
    name: str = Field(..., min_length=1, description="Display name for the agent")
    domain: str = Field(..., min_length=1, description="Task domain, e.g. 'E-commerce support'")
    system_prompt: str = Field(..., min_length=1, description="The agent's system prompt / persona")
    tools: list[ToolDefinition] = Field(default=[], description="List of tools the agent has access to")
    version: str = Field(default="1.0.0", description="Agent version for regression tracking")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode="after")
    def unique_tools(self):
        _check_unique_tools(self.tools)
        return self


class AgentUpdate(BaseModel):
    """Partial update. Changing the prompt/tools without a new version is allowed,
    but bumping `version` is what makes the regression diff meaningful."""
    name: Optional[str] = None
    domain: Optional[str] = None
    system_prompt: Optional[str] = None
    tools: Optional[list[ToolDefinition]] = None
    version: Optional[str] = None

    @model_validator(mode="after")
    def unique_tools(self):
        if self.tools is not None:
            _check_unique_tools(self.tools)
        return self


class AgentConfigInDB(AgentConfig):
    id: str = Field(..., alias="_id")

    model_config = ConfigDict(populate_by_name=True)
