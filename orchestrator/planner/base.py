"""Planner protocol and the validation error type shared by all planners."""

from __future__ import annotations

from typing import Protocol

from ..models import Goal, Plan, SkillSpec


class PlanValidationError(Exception):
    """Raised when a proposed plan fails the typed-DAG/entity checks.

    The message is precise and human-readable so it can be fed straight back to
    the LLM planner as a repair instruction.
    """


class Planner(Protocol):
    async def plan(self, goal: Goal, catalog: list[SkillSpec]) -> Plan:  # pragma: no cover
        ...
