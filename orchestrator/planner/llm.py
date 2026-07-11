"""
LLM planner — Claude composes the workflow DAG.

Uses Claude (``claude-opus-4-8``) with adaptive thinking and structured outputs
(``messages.parse``) to emit a :class:`PlanDraft` (steps + final_step). We attach
the server-side goal ourselves — the model never restates it — then validate the
result against the registry. On a validation error we re-prompt with the exact
message (bounded repair rounds); if the model can't produce a valid plan, or the
SDK/credentials are unavailable, we fall back to the deterministic heuristic
planner so ``/goal`` always degrades gracefully.

API specifics confirmed against the claude-api reference: model ``claude-opus-4-8``,
``thinking={"type": "adaptive"}`` (no ``budget_tokens`` — it 400s on this model),
``client.messages.parse(output_format=...)`` -> ``response.parsed_output``.
"""

from __future__ import annotations

import logging

from pydantic import BaseModel, Field

from .. import config
from ..entities import Entity, EntityStore
from ..models import Goal, Plan, SkillSpec, WorkflowStep
from ..skills.registry import SkillRegistry
from .base import PlanValidationError
from .heuristic import HeuristicPlanner
from .prompt import SYSTEM_PROMPT, build_user_prompt
from .validate import validate_plan

log = logging.getLogger(__name__)


class PlanDraft(BaseModel):
    """What the model emits — the goal is attached server-side, not by the model."""

    steps: list[WorkflowStep]
    final_step: str


class LLMPlanner:
    def __init__(
        self,
        registry: SkillRegistry,
        entity_store: EntityStore | None = None,
        *,
        model: str | None = None,
        max_repair_rounds: int = 2,
        max_tokens: int = 16000,
        client=None,
    ):
        self.registry = registry
        self.entity_store = entity_store
        self.model = model or config.ANTHROPIC_MODEL
        self.max_repair_rounds = max_repair_rounds
        self.max_tokens = max_tokens
        if client is not None:
            self.client = client
        else:
            import anthropic  # imported lazily so the package works without the SDK

            self.client = anthropic.AsyncAnthropic()

    async def plan(self, goal: Goal, catalog: list[SkillSpec]) -> Plan:
        cast = self._cast(goal)
        messages = [{"role": "user", "content": build_user_prompt(goal, catalog, cast)}]

        last_error: Exception | None = None
        for _ in range(self.max_repair_rounds + 1):
            try:
                draft = await self._draft(messages)
            except Exception as exc:  # noqa: BLE001 - API/SDK failure -> fall back
                log.warning("LLM planner request failed (%s); using heuristic", exc)
                return await HeuristicPlanner(self.registry).plan(goal, catalog)

            plan = Plan(goal=goal, steps=draft.steps, final_step=draft.final_step)
            try:
                validate_plan(plan, self.registry, goal)  # structural validation
                return plan
            except PlanValidationError as exc:
                last_error = exc
                messages += [
                    {"role": "assistant", "content": plan.model_dump_json()},
                    {
                        "role": "user",
                        "content": (
                            f"That plan is invalid: {exc}. Return a corrected plan "
                            "as JSON matching the schema."
                        ),
                    },
                ]

        log.warning("LLM planner exhausted repairs (%s); using heuristic", last_error)
        return await HeuristicPlanner(self.registry).plan(goal, catalog)

    async def _draft(self, messages: list[dict]) -> PlanDraft:
        response = await self.client.messages.parse(
            model=self.model,
            max_tokens=self.max_tokens,
            thinking={"type": "adaptive"},
            system=SYSTEM_PROMPT,
            messages=messages,
            output_format=PlanDraft,
        )
        return response.parsed_output

    def _cast(self, goal: Goal) -> list[Entity]:
        if self.entity_store is None:
            return []
        return [
            self.entity_store.get(ref.entity_id)
            for ref in goal.cast
            if self.entity_store.has(ref.entity_id)
        ]
