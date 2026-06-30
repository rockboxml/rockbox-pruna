"""An uploaded reference image becomes the baseline; casting skips generation."""

from __future__ import annotations

from orchestrator.models import MediaType
from orchestrator.planner.casting import resolve_entity
from orchestrator.skills.base import Skill
from orchestrator.skills.generate_image import FakeImageSkill, _spec


class _CountingImageSkill(Skill):
    spec = _spec()

    def __init__(self):
        self.calls = 0
        self._inner = FakeImageSkill()

    async def run(self, inputs, params, entities, store):
        self.calls += 1
        return await self._inner.run(inputs, params, entities, store)


async def test_uploaded_reference_skips_generation(store, maya):
    reg_skill = _CountingImageSkill()

    from orchestrator.skills.registry import SkillRegistry

    reg = SkillRegistry()
    reg.register(reg_skill)

    # Simulate the upload endpoint: attach an image reference to the entity.
    uploaded = store.put_bytes(
        b"\x89PNG-uploaded", MediaType.IMAGE, produced_by="upload", entity_id=maya.id
    )
    maya.references.append(uploaded)

    await resolve_entity(maya, reg, store)

    assert reg_skill.calls == 0  # generation skipped
    assert maya.resolved
    images = [r for r in maya.references if r.media_type == MediaType.IMAGE]
    assert images == [uploaded]  # the upload is the only baseline


async def test_without_upload_generation_runs(store, maya):
    reg_skill = _CountingImageSkill()

    from orchestrator.skills.registry import SkillRegistry

    reg = SkillRegistry()
    reg.register(reg_skill)

    await resolve_entity(maya, reg, store)

    assert reg_skill.calls == 1  # no upload -> baseline is generated
    assert any(r.media_type == MediaType.IMAGE for r in maya.references)
