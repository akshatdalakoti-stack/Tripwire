"""
models/agent.py — Agent configuration schema.
Defines what an AI agent looks like inside Tripwire.
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, timezone


class ToolDefinition(BaseModel):
    name: str = Field(..., description="Tool function name, e.g. 'send_email'")
    description: str = Field(..., description="What this tool does")
    is_destructive: bool = Field(
        default=False,
        description="True if this tool performs irreversible actions (delete, send, pay)"
    )


class AgentConfig(BaseModel):
    name: str = Field(..., description="Display name for the agent")
    domain: str = Field(..., description="Task domain, e.g. 'E-commerce support'")
    system_prompt: str = Field(..., description="The agent's system prompt / persona")
    tools: list[ToolDefinition] = Field(default=[], description="List of tools the agent has access to")
    version: str = Field(default="1.0.0", description="Agent version for regression tracking")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AgentConfigInDB(AgentConfig):
    id: str = Field(..., alias="_id")

    class Config:
        populate_by_name = True
