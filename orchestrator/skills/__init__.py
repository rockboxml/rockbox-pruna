"""
Skill auto-discovery.

Importing this package populates the process-global ``REGISTRY``. Which concrete
backend fills each capability is resolved from config:

- ``generate_image``: the Pruna server (``PRUNA_URL``) if set, else a fake.
- ``generate_video`` / ``generate_audio`` / ``stitch``: real Runway/ffmpeg
  backends when available (Phase 5), else fakes so multi-modal workflows still
  compose and run offline.

Adding a new capability is one import + one ``REGISTRY.register(...)`` line here
(or dropping a ``SKILL.md`` the loader discovers) — no planner/executor changes.
"""

from __future__ import annotations

from .. import config
from .registry import REGISTRY, SkillRegistry
from .base import Skill


def _register_defaults(registry: SkillRegistry) -> None:
    # --- image: Pruna server, or fake when no GPU service is configured ---
    from .generate_image import FakeImageSkill, PrunaGenerateImageSkill

    if config.PRUNA_URL:
        registry.register(PrunaGenerateImageSkill(config.PRUNA_URL))
    else:
        registry.register(FakeImageSkill())

    # --- video / audio / stitch ---
    real_runway = False
    if config.RUNWAYML_API_SECRET:
        try:
            from .runway import register_runway_skills

            real_runway = register_runway_skills(registry)
        except Exception as exc:  # noqa: BLE001 - never let optional backend break import
            import logging

            logging.getLogger(__name__).warning("Runway skills unavailable: %s", exc)

    if not real_runway:
        from .fakes import FakeStitchSkill, FakeTTSSkill, FakeVideoSkill

        for skill in (FakeVideoSkill(), FakeTTSSkill(), FakeStitchSkill()):
            if not registry.has(skill.spec.id):
                registry.register(skill)


_register_defaults(REGISTRY)

__all__ = ["REGISTRY", "SkillRegistry", "Skill"]
