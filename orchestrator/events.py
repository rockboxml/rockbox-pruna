"""
Lightweight event + HITL types shared by the executor and the runtime.

Kept in their own module so ``executor.py`` and ``runtime.py`` can both import
them with no circular dependency (the runtime imports the executor only inside a
function body).
"""

from __future__ import annotations

import time
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class EventType(str, Enum):
    RUN_STARTED = "run.started"
    PLAN_PROPOSED = "plan.proposed"
    STEP_STARTED = "step.started"
    STEP_MESSAGE = "step.message"
    STEP_ARTIFACT = "step.artifact"
    STEP_COMPLETED = "step.completed"
    HITL_REQUESTED = "hitl.requested"
    HITL_RESOLVED = "hitl.resolved"
    RUN_COMPLETED = "run.completed"
    RUN_ERROR = "run.error"


class Choice(BaseModel):
    """A selectable option presented to the user during a HITL pause."""

    id: str
    label: str
    kind: str = "generic"  # keep | regenerate | approve | cancel | generic


class HitlRequest(BaseModel):
    """A request for human input, raised by the executor and bridged by the run."""

    request_id: str
    step_id: str
    skill_id: str
    kind: str  # plan_approval | artifact_approval | elicitation
    prompt: str
    choices: list[Choice] = Field(default_factory=list)
    artifact: dict | None = None


class HitlDecision(BaseModel):
    """The user's resolution of a :class:`HitlRequest`."""

    request_id: str
    choice_id: str
    notes: str | None = None


class Event(BaseModel):
    """One timeline event, streamed to the UI over SSE."""

    seq: int
    run_id: str
    type: EventType
    ts: float = Field(default_factory=time.time)
    step_id: str | None = None
    skill_id: str | None = None
    message: str | None = None
    status: str | None = None  # pending | running | done | waiting | error | cancelled
    artifact: dict | None = None
    request_id: str | None = None
    prompt: str | None = None
    choices: list[Choice] = Field(default_factory=list)
    plan: dict | None = None
    data: dict[str, Any] = Field(default_factory=dict)
