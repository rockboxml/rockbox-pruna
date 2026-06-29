"""
The orchestration pipeline: goal in, executed workflow out.

Ties the pieces together so both the HTTP API and tests share one code path:

    casting (resolve cast baselines)
      -> plan (LLM or heuristic)
      -> bind (thread the cast through every step)
      -> validate (typed-DAG + entity checks)
      -> execute (run the DAG)
"""

from __future__ import annotations

from . import config
from .artifacts import ArtifactStore
from .entities import EntityStore
from .executor import execute
from .models import EntityType, ExecutionResult, Goal, Plan
from .planner.base import Planner
from .planner.binder import bind_plan
from .planner.casting import resolve_cast
from .planner.heuristic import HeuristicPlanner
from .planner.validate import validate_plan
from .skills.registry import SkillRegistry


def get_planner(
    registry: SkillRegistry, entity_store: EntityStore | None = None
) -> Planner:
    """Return the configured planner (LLM when available, else heuristic)."""
    if config.use_llm_planner():
        try:
            from .planner.llm import LLMPlanner

            return LLMPlanner(registry, entity_store)
        except Exception:  # noqa: BLE001 - fall back if SDK/config is unavailable
            pass
    return HeuristicPlanner(registry)


async def make_plan(
    goal: Goal,
    registry: SkillRegistry,
    store: ArtifactStore,
    entity_store: EntityStore,
    planner: Planner | None = None,
) -> Plan:
    """Cast → plan → bind → validate, returning an executable plan."""
    # 1. Casting: resolve baselines for every cast entity (cached on the entity).
    cast = [entity_store.get(ref.entity_id) for ref in goal.cast if entity_store.has(ref.entity_id)]
    await resolve_cast(cast, registry, store)

    # 2. Plan.
    planner = planner or get_planner(registry, entity_store)
    plan = await planner.plan(goal, registry.catalog())
    plan.goal = goal  # never trust a planner's echo of the goal

    # 3. Bind the cast into the plan (returns entity-type map for validation).
    entity_types = bind_plan(plan, goal, entity_store, registry)

    # 4. Validate (raises PlanValidationError on any problem).
    validate_plan(plan, registry, goal, entity_types)
    return plan


async def run_goal(
    goal: Goal,
    registry: SkillRegistry,
    store: ArtifactStore,
    entity_store: EntityStore,
    planner: Planner | None = None,
) -> ExecutionResult:
    """Plan and execute a goal end to end."""
    plan = await make_plan(goal, registry, store, entity_store, planner)
    return await execute(plan, registry, store, entity_store)
