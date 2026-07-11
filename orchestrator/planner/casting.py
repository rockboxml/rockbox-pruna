"""
Casting — resolve cast entities to baseline reference artifacts.

Before the main workflow runs, each referenced Character/Location is "cast": its
canonical visual baseline (a portrait / establishing shot) is generated once from
its descriptors via the image skill, and a voice baseline is recorded for
characters. The baseline artifacts are stored on the entity so later runs reuse
them — this is what makes a character/location consistent across many goals.

The binder then threads these baselines into every relevant step.
"""

from __future__ import annotations

from ..artifacts import ArtifactStore
from ..entities import Character, Entity, Location
from ..models import EntityType, MediaArtifact, MediaType
from ..skills.registry import SkillRegistry


async def resolve_entity(
    entity: Entity,
    registry: SkillRegistry,
    store: ArtifactStore,
    *,
    force: bool = False,
) -> Entity:
    """Materialize ``entity``'s baseline reference artifact(s) if not already done."""
    if entity.resolved and not force:
        return entity

    visual = _existing_visual(entity)
    if visual is None and registry.has("generate_image"):
        skill = registry.get("generate_image")
        prompt = _baseline_prompt(entity)
        outputs = await skill.run(
            inputs={}, params={"prompt": prompt}, entities=[entity], store=store
        )
        art = outputs["image"]
        # Re-tag as this entity's baseline (content-addressed id is unchanged).
        baseline = art.model_copy(
            update={"entity_id": entity.id, "produced_by": "cast"}
        )
        entity.references.append(baseline)

    entity.resolved = True
    return entity


async def resolve_cast(
    entities: list[Entity],
    registry: SkillRegistry,
    store: ArtifactStore,
) -> list[Entity]:
    """Resolve a whole cast (sequentially; baselines are cheap and cached)."""
    for entity in entities:
        await resolve_entity(entity, registry, store)
    return entities


def _existing_visual(entity: Entity) -> MediaArtifact | None:
    return next(
        (r for r in entity.references if r.media_type == MediaType.IMAGE), None
    )


def _baseline_prompt(entity: Entity) -> str:
    if isinstance(entity, Character):
        bits = [
            f"character portrait of {entity.name}",
            entity.appearance,
            entity.style,
        ]
    elif isinstance(entity, Location):
        bits = [
            f"establishing shot of {entity.name}",
            entity.appearance,
            entity.style,
        ]
    else:
        bits = [entity.name, entity.descriptor_text()]
    return ", ".join(b for b in bits if b)
