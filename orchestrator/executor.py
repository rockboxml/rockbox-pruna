"""
Workflow executor.

Runs a validated :class:`Plan` as an async DAG: steps execute in dependency
"waves" (independent branches run concurrently), each step's inputs are resolved
from upstream outputs / goal seed inputs / bound entity baselines, the resolved
artifact type is re-checked against the port at runtime, and failures are
retried with backoff and isolated to their branch.
"""

from __future__ import annotations

import asyncio
import time

from .artifacts import ArtifactStore
from .entities import Entity, EntityStore
from .models import (
    ExecutionResult,
    Goal,
    MediaArtifact,
    Plan,
    StepResult,
    StepStatus,
    WorkflowStep,
)
from .planner.validate import topo_order
from .skills.registry import SkillRegistry


async def execute(
    plan: Plan,
    registry: SkillRegistry,
    store: ArtifactStore,
    entity_store: EntityStore | None = None,
    *,
    max_retries: int = 2,
    concurrency: int = 4,
    backoff_base: float = 0.2,
) -> ExecutionResult:
    """Execute ``plan`` and return an :class:`ExecutionResult`."""
    order = topo_order(plan)
    steps = {s.id: s for s in plan.steps}
    deps = _dependencies(plan)
    sem = asyncio.Semaphore(concurrency)

    outputs: dict[str, dict[str, MediaArtifact]] = {}
    results: dict[str, StepResult] = {}

    # Group steps into waves by dependency depth so independent branches run
    # concurrently while respecting edges.
    for wave in _waves(order, deps):
        async def run_one(step_id: str) -> None:
            step = steps[step_id]
            # Skip if any dependency failed/was skipped.
            failed_dep = next(
                (d for d in deps[step_id] if results.get(d) and results[d].status != StepStatus.OK),
                None,
            )
            if failed_dep is not None:
                results[step_id] = StepResult(
                    step_id=step_id,
                    skill_id=step.skill_id,
                    status=StepStatus.SKIPPED,
                    error=f"upstream step '{failed_dep}' did not succeed",
                )
                return
            async with sem:
                results[step_id] = await _run_step(
                    step, plan.goal, registry, store, entity_store, outputs,
                    max_retries=max_retries, backoff_base=backoff_base,
                )
                if results[step_id].status == StepStatus.OK:
                    outputs[step_id] = results[step_id].outputs

        await asyncio.gather(*(run_one(sid) for sid in wave))

    final = results.get(plan.final_step)
    final_artifacts = list(final.outputs.values()) if final and final.status == StepStatus.OK else []
    return ExecutionResult(
        plan=plan,
        step_results=results,
        final_artifacts=final_artifacts,
        ok=bool(final_artifacts),
    )


async def _run_step(
    step: WorkflowStep,
    goal: Goal,
    registry: SkillRegistry,
    store: ArtifactStore,
    entity_store: EntityStore | None,
    outputs: dict[str, dict[str, MediaArtifact]],
    *,
    max_retries: int,
    backoff_base: float,
) -> StepResult:
    skill = registry.get(step.skill_id)
    spec = skill.spec
    inputs = _resolve_inputs(step, spec, goal, outputs)
    entities = _resolve_entities(step, entity_store)

    started = time.monotonic()
    attempt = 0
    last_err: Exception | None = None
    while attempt <= max_retries:
        attempt += 1
        try:
            produced = await skill.run(inputs, dict(step.params), entities, store)
            _check_outputs(spec, produced)
            return StepResult(
                step_id=step.id,
                skill_id=step.skill_id,
                status=StepStatus.OK,
                outputs=produced,
                attempts=attempt,
                duration_s=time.monotonic() - started,
            )
        except Exception as exc:  # noqa: BLE001 - record and (maybe) retry
            last_err = exc
            if attempt <= max_retries:
                await asyncio.sleep(backoff_base * (2 ** (attempt - 1)))

    return StepResult(
        step_id=step.id,
        skill_id=step.skill_id,
        status=StepStatus.ERROR,
        error=f"{type(last_err).__name__}: {last_err}",
        attempts=attempt,
        duration_s=time.monotonic() - started,
    )


def _resolve_inputs(step, spec, goal: Goal, outputs) -> dict[str, MediaArtifact]:
    resolved: dict[str, MediaArtifact] = {}
    for port_name, binding in step.input_bindings.items():
        port = spec.input(port_name)
        if binding.from_step is not None:
            artifact = outputs.get(binding.from_step, {}).get(binding.port)
        elif binding.from_goal is not None:
            artifact = goal.seed_inputs[binding.from_goal]
        else:
            artifact = None
        if artifact is None:
            raise RuntimeError(f"input '{port_name}' could not be resolved")
        # Runtime type check — even after static validation, confirm the actual
        # artifact matches the declared port type.
        if port is not None and artifact.media_type != port.media_type:
            raise RuntimeError(
                f"input '{port_name}' resolved to {artifact.media_type.value}, "
                f"expected {port.media_type.value}"
            )
        resolved[port_name] = artifact
    return resolved


def _resolve_entities(step, entity_store: EntityStore | None) -> list[Entity]:
    if entity_store is None:
        return []
    out: list[Entity] = []
    for ref in step.entity_refs:
        if entity_store.has(ref.entity_id):
            out.append(entity_store.get(ref.entity_id))
    return out


def _check_outputs(spec, produced: dict[str, MediaArtifact]) -> None:
    for port in spec.outputs:
        if port.name not in produced:
            raise RuntimeError(f"skill '{spec.id}' did not produce output '{port.name}'")
        if produced[port.name].media_type != port.media_type:
            raise RuntimeError(
                f"skill '{spec.id}' output '{port.name}' is "
                f"{produced[port.name].media_type.value}, expected {port.media_type.value}"
            )


def _dependencies(plan: Plan) -> dict[str, set[str]]:
    deps: dict[str, set[str]] = {s.id: set() for s in plan.steps}
    for step in plan.steps:
        for binding in step.input_bindings.values():
            if binding.from_step is not None:
                deps[step.id].add(binding.from_step)
    return deps


def _waves(order: list[str], deps: dict[str, set[str]]) -> list[list[str]]:
    """Partition steps into dependency waves preserving topological order."""
    depth: dict[str, int] = {}
    for sid in order:
        depth[sid] = 1 + max((depth[d] for d in deps[sid]), default=-1)
    waves: dict[int, list[str]] = {}
    for sid in order:
        waves.setdefault(depth[sid], []).append(sid)
    return [waves[k] for k in sorted(waves)]
