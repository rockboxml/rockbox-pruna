"""
The Skill abstraction.

A skill declares a typed IO contract (``spec``) and an async ``run``. The
executor calls ``run`` with the resolved input artifacts, the step params, the
resolved cast entities (for prompt/param conditioning), and the artifact store.
``run`` returns a mapping of output-port name -> produced artifact.

Keeping skills to this narrow contract is what makes them composable: the
planner reasons over ``spec`` alone, and the executor never needs to know what a
skill does internally.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..artifacts import ArtifactStore
from ..entities import Entity
from ..models import MediaArtifact, SkillSpec


class Skill(ABC):
    """Base class for all skills. Subclasses set ``spec`` and implement ``run``."""

    spec: SkillSpec

    @abstractmethod
    async def run(
        self,
        inputs: dict[str, MediaArtifact],
        params: dict[str, object],
        entities: list[Entity],
        store: ArtifactStore,
    ) -> dict[str, MediaArtifact]:
        """Execute the skill and return {output_port_name: artifact}."""
        raise NotImplementedError

    @property
    def id(self) -> str:
        return self.spec.id
