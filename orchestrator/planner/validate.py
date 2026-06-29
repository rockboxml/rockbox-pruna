"""
Plan validation — the real type-safety layer.

The LLM proposes; this validator disposes. A structured-output JSON schema can
guarantee the *shape* of a ``Plan`` but not that step inputs are satisfied by
upstream outputs of the same media type, that params match each skill's schema,
or that entity references are legal. Those are runtime facts checked here, so a
plan that passes ``validate_plan`` is safe to execute.
"""

from __future__ import annotations

from ..models import (
    EntityType,
    Goal,
    MediaType,
    Plan,
    SkillSpec,
    WorkflowStep,
)
from ..skills.registry import SkillRegistry
from .base import PlanValidationError


def validate_plan(
    plan: Plan,
    registry: SkillRegistry,
    goal: Goal,
    entity_types: dict[str, EntityType] | None = None,
) -> None:
    """Validate ``plan`` against the registry and goal. Raise on any problem.

    ``entity_types`` maps cast entity id -> kind; when provided, the validator also
    enforces that each step's skill ``accepts_entities`` the referenced kind.
    """
    cast_ids = {ref.entity_id for ref in goal.cast}
    by_id: dict[str, WorkflowStep] = {}

    # 1. Unique step ids + known skills.
    for step in plan.steps:
        if step.id in by_id:
            raise PlanValidationError(f"duplicate step id '{step.id}'")
        by_id[step.id] = step
        if not registry.has(step.skill_id):
            raise PlanValidationError(
                f"step '{step.id}' uses unknown skill '{step.skill_id}'"
            )

    # 2. Acyclic + topo-sortable (also catches references to unknown steps).
    order = topo_order(plan)

    # 3/4/5. Per-step: bindings type-check, params, entity refs.
    specs = {s.id: registry.get(s.skill_id).spec for s in plan.steps}
    for step in plan.steps:
        spec = specs[step.id]
        _validate_bindings(step, spec, by_id, specs, goal)
        _validate_params(step, spec)
        _validate_entities(step, spec, cast_ids, entity_types)

    # 6. final_step exists and (optionally) matches the requested output type.
    if plan.final_step not in by_id:
        raise PlanValidationError(
            f"final_step '{plan.final_step}' is not a step in the plan"
        )
    target = goal.constraints.get("target_media_type")
    if target:
        target_mt = MediaType(target)
        final_spec = specs[plan.final_step]
        if not any(o.media_type == target_mt for o in final_spec.outputs):
            raise PlanValidationError(
                f"final_step '{plan.final_step}' (skill '{final_spec.id}') does not "
                f"produce the requested {target_mt.value}"
            )

    _ = order  # order is validated; executor recomputes it.


def topo_order(plan: Plan) -> list[str]:
    """Return step ids in dependency order; raise on cycles/unknown deps."""
    ids = {s.id for s in plan.steps}
    deps: dict[str, set[str]] = {s.id: set() for s in plan.steps}
    for step in plan.steps:
        for binding in step.input_bindings.values():
            if binding.from_step is not None:
                if binding.from_step not in ids:
                    raise PlanValidationError(
                        f"step '{step.id}' binds from unknown step "
                        f"'{binding.from_step}'"
                    )
                deps[step.id].add(binding.from_step)

    order: list[str] = []
    done: set[str] = set()
    temp: set[str] = set()

    def visit(node: str) -> None:
        if node in done:
            return
        if node in temp:
            raise PlanValidationError(f"cycle detected at step '{node}'")
        temp.add(node)
        for d in deps[node]:
            visit(d)
        temp.discard(node)
        done.add(node)
        order.append(node)

    for node in deps:
        visit(node)
    return order


def _validate_bindings(
    step: WorkflowStep,
    spec: SkillSpec,
    by_id: dict[str, WorkflowStep],
    specs: dict[str, SkillSpec],
    goal: Goal,
) -> None:
    known_ports = {p.name for p in spec.inputs}
    for port_name in step.input_bindings:
        if port_name not in known_ports:
            raise PlanValidationError(
                f"step '{step.id}' binds unknown input port '{port_name}' "
                f"on skill '{spec.id}'"
            )

    for port in spec.inputs:
        binding = step.input_bindings.get(port.name)
        if binding is None:
            if port.required:
                raise PlanValidationError(
                    f"step '{step.id}' is missing required input '{port.name}'"
                )
            continue

        # Resolve the bound source's media type.
        if binding.from_step is not None:
            up_spec = specs[binding.from_step]
            up_port = up_spec.output(binding.port) if binding.port else None
            if up_port is None:
                raise PlanValidationError(
                    f"step '{step.id}' input '{port.name}' binds output "
                    f"'{binding.port}' of step '{binding.from_step}', which does "
                    f"not exist on skill '{up_spec.id}'"
                )
            src_mt = up_port.media_type
        elif binding.from_goal is not None:
            if not (0 <= binding.from_goal < len(goal.seed_inputs)):
                raise PlanValidationError(
                    f"step '{step.id}' input '{port.name}' binds goal seed "
                    f"#{binding.from_goal}, which is out of range"
                )
            src_mt = goal.seed_inputs[binding.from_goal].media_type
        else:
            raise PlanValidationError(
                f"step '{step.id}' input '{port.name}' has no source "
                "(set from_step or from_goal)"
            )

        if src_mt != port.media_type:
            raise PlanValidationError(
                f"step '{step.id}' input '{port.name}' expects "
                f"{port.media_type.value} but is bound to a {src_mt.value} source"
            )


_JSON_PY_TYPES = {
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "object": dict,
    "array": list,
}


def _validate_params(step: WorkflowStep, spec: SkillSpec) -> None:
    """Lightweight JSON-Schema-subset check of step.params against params_schema."""
    schema = spec.params_schema or {}
    props = schema.get("properties", {})
    required = schema.get("required", [])
    additional = schema.get("additionalProperties", True)

    for key in required:
        if key not in step.params:
            raise PlanValidationError(
                f"step '{step.id}' is missing required param '{key}'"
            )

    for key, value in step.params.items():
        if key not in props:
            if additional is False:
                raise PlanValidationError(
                    f"step '{step.id}' has unknown param '{key}' for skill '{spec.id}'"
                )
            continue
        _check_type(step.id, key, value, props[key])


def _check_type(step_id: str, key: str, value, prop_schema: dict) -> None:
    declared = prop_schema.get("type")
    if declared is None or value is None:
        return
    types = declared if isinstance(declared, list) else [declared]
    if "null" in types and value is None:
        return
    py_types: tuple = tuple(
        t
        for name in types
        if name != "null"
        for t in (
            _JSON_PY_TYPES[name]
            if isinstance(_JSON_PY_TYPES.get(name), tuple)
            else (_JSON_PY_TYPES.get(name),)
        )
        if t is not None
    )
    if not py_types:
        return
    # bool is a subclass of int; reject it when only integer/number is allowed.
    if isinstance(value, bool) and bool not in py_types:
        raise PlanValidationError(
            f"step '{step_id}' param '{key}' should be {types}, got bool"
        )
    if not isinstance(value, py_types):
        raise PlanValidationError(
            f"step '{step_id}' param '{key}' should be {types}, got "
            f"{type(value).__name__}"
        )


def _validate_entities(
    step: WorkflowStep,
    spec: SkillSpec,
    cast_ids: set[str],
    entity_types: dict[str, EntityType] | None,
) -> None:
    for ref in step.entity_refs:
        if ref.entity_id not in cast_ids:
            raise PlanValidationError(
                f"step '{step.id}' references entity '{ref.entity_id}' that is not "
                "in the goal cast"
            )
        if entity_types is not None:
            etype = entity_types.get(ref.entity_id)
            if etype is not None and etype not in spec.accepts_entities:
                raise PlanValidationError(
                    f"step '{step.id}' (skill '{spec.id}') references "
                    f"{etype.value} '{ref.entity_id}', but the skill does not accept "
                    f"{etype.value} entities"
                )
