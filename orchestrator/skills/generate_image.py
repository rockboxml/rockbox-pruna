"""
The ``generate_image`` skill — the ``rw-generate-image`` analog.

Two interchangeable implementations share the same ``spec.id`` so the rest of the
system is oblivious to which is active:

- :class:`PrunaGenerateImageSkill` calls the existing ``server.py`` over HTTP.
- :class:`FakeImageSkill` synthesizes a tiny PNG with no network — used for
  GPU-free thin-slice runs and tests.

Both expose an optional ``reference_image`` port (the consistency hook). The
Pruna SD model ignores it today; descriptor-merge into the prompt still delivers
baseline continuity, and a future gen4-style model would use the reference image
directly. The same contract is reused by the Runway adapter, where the reference
image is honoured by ``gen4_image``.
"""

from __future__ import annotations

import hashlib

import httpx

from ..artifacts import ArtifactStore
from ..entities import Entity
from ..models import (
    EntityType,
    MediaArtifact,
    MediaType,
    PortKind,
    PortSpec,
    SkillSpec,
)
from ._png import solid_png
from .base import Skill

_PARAMS_SCHEMA = {
    "type": "object",
    "properties": {
        "prompt": {"type": "string"},
        "num_inference_steps": {"type": "integer"},
        "guidance_scale": {"type": "number"},
        "seed": {"type": ["integer", "null"]},
    },
    "required": ["prompt"],
    "additionalProperties": False,
}


def _spec() -> SkillSpec:
    return SkillSpec(
        id="generate_image",
        description=(
            "Generate an image from a text prompt, optionally conditioned on a "
            "reference image (for character/location consistency). Use as the "
            "first step when a goal needs an image and none is supplied."
        ),
        inputs=[
            PortSpec(
                name="reference_image",
                media_type=MediaType.IMAGE,
                required=False,
                kind=PortKind.REFERENCE,
                description="Reference image to keep a character/location on-model.",
            )
        ],
        outputs=[PortSpec(name="image", media_type=MediaType.IMAGE)],
        params_schema=_PARAMS_SCHEMA,
        accepts_entities=[EntityType.CHARACTER, EntityType.LOCATION],
        cost_hint=2.0,
        latency_hint_s=8.0,
        tags=["generative", "image"],
    )


def build_prompt(params: dict, entities: list[Entity]) -> str:
    """Merge entity descriptors into the base prompt for conditioning."""
    base = str(params.get("prompt", "")).strip()
    descriptors = [e.descriptor_text() for e in entities if e.descriptor_text()]
    if descriptors:
        joined = " | ".join(descriptors)
        return f"{base} ({joined})" if base else joined
    return base


class PrunaGenerateImageSkill(Skill):
    """Image generation backed by the Pruna ``server.py`` ``/generate`` endpoint."""

    spec = _spec()

    def __init__(self, base_url: str, client: httpx.AsyncClient | None = None):
        self.base_url = base_url.rstrip("/")
        self._client = client

    async def run(self, inputs, params, entities, store: ArtifactStore):
        prompt = build_prompt(params, entities)
        body: dict = {"prompt": prompt}
        for key in ("num_inference_steps", "guidance_scale", "seed"):
            if key in params and params[key] is not None:
                body[key] = params[key]

        client = self._client or httpx.AsyncClient(timeout=120)
        try:
            resp = await client.post(f"{self.base_url}/generate", json=body)
            resp.raise_for_status()
            data_url = resp.json()["image"]
        finally:
            if self._client is None:
                await client.aclose()

        artifact = store.put_data_url(
            data_url, MediaType.IMAGE, meta={"prompt": prompt}
        )
        return {"image": artifact}


class FakeImageSkill(Skill):
    """No-network image skill: a solid PNG whose colour is derived from the prompt.

    Distinct prompts produce distinct bytes (and thus distinct content-addressed
    ids), which lets tests assert on artifact identity and continuity.
    """

    spec = _spec()

    async def run(self, inputs, params, entities, store: ArtifactStore):
        prompt = build_prompt(params, entities)
        digest = hashlib.sha256(prompt.encode()).digest()
        png = solid_png(digest[0], digest[1], digest[2])
        artifact = store.put_bytes(png, MediaType.IMAGE, meta={"prompt": prompt})
        return {"image": artifact}
