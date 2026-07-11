"""
Core data models for the orchestrator.

These pydantic models are the single source of truth for the whole system: the
LLM planner emits a ``Plan`` (its JSON schema *is* the contract), the validator
type-checks it against the skill registry, and the executor runs it. Keeping the
shapes here — rather than scattering dict conventions — means the validator,
planner prompt, and executor all agree by construction.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class MediaType(str, Enum):
    """The kind of media an artifact carries or a port produces/consumes."""

    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"


class EntityType(str, Enum):
    """First-class world-model entity kinds (see ``entities.py``)."""

    CHARACTER = "character"
    LOCATION = "location"


class PortKind(str, Enum):
    """
    How a skill input port is filled.

    - ``DATA``: a normal upstream artifact or goal seed input.
    - ``REFERENCE``: an optional conditioning artifact (e.g. a reference image)
      the binder fills from a cast member's baseline for continuity.
    - ``ENTITY``: a non-artifact entity handle (e.g. a voice id) the binder fills.
    """

    DATA = "data"
    REFERENCE = "reference"
    ENTITY = "entity"


class MediaArtifact(BaseModel):
    """A typed reference to a produced/used piece of media.

    Bytes live in the :class:`~orchestrator.artifacts.ArtifactStore`; this object
    only carries the reference and metadata so it is cheap to pass around the DAG.
    """

    id: str
    media_type: MediaType
    uri: str  # file:// , data: , or https://
    mime: str | None = None
    meta: dict[str, Any] = Field(default_factory=dict)
    produced_by: str | None = None  # step id, or "cast"/"goal"
    entity_id: str | None = None  # set when this artifact is an entity baseline


class PortSpec(BaseModel):
    """A typed input or output port on a skill."""

    name: str
    media_type: MediaType
    required: bool = True
    kind: PortKind = PortKind.DATA
    description: str = ""


class SkillSpec(BaseModel):
    """The capability descriptor the planner reasons over.

    The planner sees a list of these (the *catalog*) and must produce steps whose
    bindings satisfy each input port's type from an upstream output of the same
    type or a goal seed input. ``accepts_entities`` declares which entity kinds a
    skill can be conditioned on for continuity.
    """

    id: str
    description: str
    inputs: list[PortSpec] = Field(default_factory=list)
    outputs: list[PortSpec]
    params_schema: dict[str, Any] = Field(default_factory=dict)
    accepts_entities: list[EntityType] = Field(default_factory=list)
    cost_hint: float = 1.0
    latency_hint_s: float = 5.0
    tags: list[str] = Field(default_factory=list)

    def input(self, name: str) -> PortSpec | None:
        return next((p for p in self.inputs if p.name == name), None)

    def output(self, name: str) -> PortSpec | None:
        return next((p for p in self.outputs if p.name == name), None)


class EntityRef(BaseModel):
    """A reference to a cast entity by id, used in goals and steps."""

    entity_id: str


class Goal(BaseModel):
    """The end-user's request: free text plus the cast and any seed inputs."""

    text: str
    seed_inputs: list[MediaArtifact] = Field(default_factory=list)
    cast: list[EntityRef] = Field(default_factory=list)
    constraints: dict[str, Any] = Field(default_factory=dict)


class InputBinding(BaseModel):
    """How a single input port of a step is fed.

    Exactly one source should be set. ``from_step`` references an upstream step's
    named output port; ``from_goal`` indexes ``Goal.seed_inputs``.
    """

    from_step: str | None = None
    from_goal: int | None = None
    port: str | None = None  # upstream output port name (for from_step)


class WorkflowStep(BaseModel):
    """One node in the workflow DAG."""

    id: str
    skill_id: str
    input_bindings: dict[str, InputBinding] = Field(default_factory=dict)
    params: dict[str, Any] = Field(default_factory=dict)
    entity_refs: list[EntityRef] = Field(default_factory=list)
    rationale: str = ""


class Plan(BaseModel):
    """A validated (or to-be-validated) workflow DAG."""

    goal: Goal
    steps: list[WorkflowStep]
    final_step: str

    def step(self, step_id: str) -> WorkflowStep | None:
        return next((s for s in self.steps if s.id == step_id), None)


class StepStatus(str, Enum):
    OK = "ok"
    ERROR = "error"
    SKIPPED = "skipped"


class StepResult(BaseModel):
    step_id: str
    skill_id: str
    status: StepStatus
    outputs: dict[str, MediaArtifact] = Field(default_factory=dict)
    error: str | None = None
    attempts: int = 1
    duration_s: float = 0.0


class ExecutionResult(BaseModel):
    plan: Plan
    step_results: dict[str, StepResult] = Field(default_factory=dict)
    final_artifacts: list[MediaArtifact] = Field(default_factory=list)
    ok: bool = False
