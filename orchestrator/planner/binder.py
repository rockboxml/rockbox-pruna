"""
Continuity binding.

After a plan is proposed and the cast is resolved, the binder wires the cast's
baselines into the plan so the same character/location stays on-model across
every step and modality:

1. **Default continuity** — any step whose skill ``accepts_entities`` but has no
   explicit ``entity_refs`` is bound to every accepted cast member, so the
   planner never has to remember to thread the cast through each step.
2. **Reference injection** — a step's unbound ``reference_image`` port is bound to
   a referenced entity's visual baseline (added to ``goal.seed_inputs``), making
   the consistency link explicit and validatable in the plan.
3. **Voice params** — a ``generate_audio`` step referencing a character with a
   ``voice_id`` gets that id in its params, so the narrator's voice is consistent.

Skills also receive the resolved :class:`Entity` objects at ``run`` time, so a
backend (e.g. Runway) can read all referenced baselines directly. The binder
returns the entity-type map the validator uses to enforce ``accepts_entities``.
"""

from __future__ import annotations

from ..entities import Character, Entity, EntityStore
from ..models import (
    EntityType,
    Goal,
    InputBinding,
    MediaArtifact,
    MediaType,
    Plan,
    PortKind,
    EntityRef,
)
from ..skills.registry import SkillRegistry


def bind_plan(
    plan: Plan,
    goal: Goal,
    entity_store: EntityStore,
    registry: SkillRegistry,
) -> dict[str, EntityType]:
    """Mutate ``plan``/``goal`` in place to thread the cast through every step.

    Returns a map of cast entity id -> kind for the validator.
    """
    cast: list[Entity] = [
        entity_store.get(ref.entity_id)
        for ref in goal.cast
        if entity_store.has(ref.entity_id)
    ]
    entity_types = {e.id: e.type for e in cast}
    by_id = {e.id: e for e in cast}

    for step in plan.steps:
        if not registry.has(step.skill_id):
            continue
        spec = registry.get(step.skill_id).spec
        accepts = set(spec.accepts_entities)
        if not accepts:
            continue

        # 1. Default continuity: if the planner didn't pick entities, use the
        #    whole cast (restricted to kinds this skill accepts).
        if not step.entity_refs:
            step.entity_refs = [
                EntityRef(entity_id=e.id) for e in cast if e.type in accepts
            ]
        else:
            # Keep only refs whose kind the skill accepts (avoid validation errors).
            step.entity_refs = [
                ref
                for ref in step.entity_refs
                if by_id.get(ref.entity_id) and by_id[ref.entity_id].type in accepts
            ]

        referenced = [by_id[r.entity_id] for r in step.entity_refs if r.entity_id in by_id]
        if not referenced:
            continue

        _inject_reference_image(step, spec, referenced, goal)
        _inject_voice(step, spec, referenced)

    return entity_types


def _inject_reference_image(step, spec, referenced: list[Entity], goal: Goal) -> None:
    port = next(
        (p for p in spec.inputs if p.kind == PortKind.REFERENCE and p.media_type == MediaType.IMAGE),
        None,
    )
    if port is None or port.name in step.input_bindings:
        return
    baseline = _first_visual(referenced)
    if baseline is None:
        return
    idx = _ensure_seed(goal, baseline)
    step.input_bindings[port.name] = InputBinding(from_goal=idx)


def _inject_voice(step, spec, referenced: list[Entity]) -> None:
    if spec.id != "generate_audio":
        return
    if step.params.get("voice_id"):
        return
    char = next((e for e in referenced if isinstance(e, Character)), None)
    if char and char.voice.voice_id:
        step.params["voice_id"] = char.voice.voice_id


def _first_visual(entities: list[Entity]) -> MediaArtifact | None:
    for e in entities:
        for ref in e.references:
            if ref.media_type == MediaType.IMAGE:
                return ref
    return None


def _ensure_seed(goal: Goal, artifact: MediaArtifact) -> int:
    for i, seed in enumerate(goal.seed_inputs):
        if seed.id == artifact.id:
            return i
    goal.seed_inputs.append(artifact)
    return len(goal.seed_inputs) - 1
