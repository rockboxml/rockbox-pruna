"""
First-class world-model entities: Characters and Locations.

This is the consistency engine. An entity carries human-authored *descriptors*
(a character's appearance/voice/style, a location's appearance) and, once
"cast", a set of *baseline reference artifacts* (a canonical portrait, a voice
sample/id, an establishing shot). Those baselines are produced once and then
bound into every relevant skill step so the same character looks and sounds the
same — and the same location stays coherent — across image, video, and audio.

Runway exposes character avatars but no cross-generation Character+Location
consistency framework; that gap is what this module fills.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from .models import EntityType, MediaArtifact


class VoiceKind(str, Enum):
    DESCRIPTION = "description"  # text description of the voice
    SAMPLE = "sample"  # a reference audio artifact
    VOICE_ID = "voice_id"  # a provider voice id (e.g. ElevenLabs / Runway)


class Voice(BaseModel):
    """How a character should sound. Any subset may be provided."""

    description: str = ""
    voice_id: str | None = None
    sample: MediaArtifact | None = None

    def kind(self) -> VoiceKind:
        if self.voice_id:
            return VoiceKind.VOICE_ID
        if self.sample is not None:
            return VoiceKind.SAMPLE
        return VoiceKind.DESCRIPTION


class Entity(BaseModel):
    """Base for first-class entities. ``references`` are resolved baselines."""

    id: str
    name: str
    type: EntityType
    references: list[MediaArtifact] = Field(default_factory=list)
    resolved: bool = False

    def descriptors(self) -> dict[str, str]:
        """Text descriptors merged into prompts/params for conditioning."""
        return {}

    def descriptor_text(self) -> str:
        parts = [f"{k}: {v}" for k, v in self.descriptors().items() if v]
        return "; ".join(parts)


class Character(Entity):
    type: EntityType = EntityType.CHARACTER
    appearance: str = ""
    style: str = ""
    voice: Voice = Field(default_factory=Voice)

    def descriptors(self) -> dict[str, str]:
        return {
            "name": self.name,
            "appearance": self.appearance,
            "style": self.style,
            "voice": self.voice.description,
        }


class Location(Entity):
    type: EntityType = EntityType.LOCATION
    appearance: str = ""
    style: str = ""

    def descriptors(self) -> dict[str, str]:
        return {
            "name": self.name,
            "appearance": self.appearance,
            "style": self.style,
        }


def make_entity(data: dict) -> Entity:
    """Construct the right Entity subclass from a plain dict (e.g. from JSON)."""
    etype = EntityType(data.get("type", EntityType.CHARACTER))
    if etype == EntityType.CHARACTER:
        return Character(**data)
    return Location(**data)


class EntityStore:
    """In-memory entity registry (the reusable "series bible").

    Entities persist across goals so a character is consistent across many
    workflows. Swap the dict for a database behind the same interface later.
    """

    def __init__(self) -> None:
        self._entities: dict[str, Entity] = {}

    def put(self, entity: Entity) -> Entity:
        self._entities[entity.id] = entity
        return entity

    def get(self, entity_id: str) -> Entity:
        if entity_id not in self._entities:
            raise KeyError(f"unknown entity: {entity_id}")
        return self._entities[entity_id]

    def has(self, entity_id: str) -> bool:
        return entity_id in self._entities

    def all(self) -> list[Entity]:
        return list(self._entities.values())

    def of_type(self, etype: EntityType) -> list[Entity]:
        return [e for e in self._entities.values() if e.type == etype]
