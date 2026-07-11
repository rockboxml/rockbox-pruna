from orchestrator.models import MediaType
from orchestrator.planner.casting import resolve_cast, resolve_entity


async def test_character_resolves_to_visual_baseline(registry, store, maya):
    await resolve_entity(maya, registry, store)
    assert maya.resolved
    images = [r for r in maya.references if r.media_type == MediaType.IMAGE]
    assert len(images) == 1
    assert images[0].entity_id == "maya"
    assert images[0].produced_by == "cast"


async def test_resolution_is_cached(registry, store, maya):
    await resolve_entity(maya, registry, store)
    first = list(maya.references)
    await resolve_entity(maya, registry, store)  # second pass is a no-op
    assert maya.references == first


async def test_resolve_cast_resolves_all(registry, store, maya, apartment):
    out = await resolve_cast([maya, apartment], registry, store)
    assert all(e.resolved for e in out)
    assert all(
        any(r.media_type == MediaType.IMAGE for r in e.references) for e in out
    )
