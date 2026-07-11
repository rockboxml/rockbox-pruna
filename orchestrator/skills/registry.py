"""
Skill registry.

A process-global registry that maps skill id -> Skill instance. Importing the
``skills`` package registers every skill, so the catalog the planner sees is
just whatever has been imported. ``producers_of`` powers the heuristic planner's
backward chaining.
"""

from __future__ import annotations

from ..models import MediaType, SkillSpec
from .base import Skill


class SkillRegistry:
    def __init__(self) -> None:
        self._skills: dict[str, Skill] = {}

    def register(self, skill: Skill) -> Skill:
        """Register (or replace) a skill by its spec id. Returns it for chaining."""
        self._skills[skill.spec.id] = skill
        return skill

    def unregister(self, skill_id: str) -> None:
        self._skills.pop(skill_id, None)

    def has(self, skill_id: str) -> bool:
        return skill_id in self._skills

    def get(self, skill_id: str) -> Skill:
        if skill_id not in self._skills:
            raise KeyError(f"unknown skill: {skill_id}")
        return self._skills[skill_id]

    def catalog(self) -> list[SkillSpec]:
        """The list of capability descriptors the planner reasons over."""
        return [s.spec for s in self._skills.values()]

    def ids(self) -> list[str]:
        return list(self._skills.keys())

    def producers_of(self, media_type: MediaType) -> list[SkillSpec]:
        """Skills that can produce an output of ``media_type``, cheapest first."""
        specs = [
            s.spec
            for s in self._skills.values()
            if any(o.media_type == media_type for o in s.spec.outputs)
        ]
        return sorted(specs, key=lambda sp: sp.cost_hint)


# Process-global registry. ``skills/__init__.py`` populates it on import.
REGISTRY = SkillRegistry()
