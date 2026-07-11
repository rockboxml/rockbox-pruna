"""
No-network fake skills for video, audio, and stitching.

These let the planner compose and the executor run multi-modal workflows
("a video of X narrating in Y") entirely offline — for the GPU-free thin slice,
for tests, and as placeholders until the real Runway/ffmpeg backends are wired
in. They honour the same typed contracts (and ``accepts_entities``) as their real
counterparts, so swapping in a real backend changes nothing upstream.
"""

from __future__ import annotations

import hashlib

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
from .base import Skill


def _fingerprint(*parts: str) -> bytes:
    h = hashlib.sha256()
    for p in parts:
        h.update(p.encode())
        h.update(b"\x00")
    return h.digest()


class FakeVideoSkill(Skill):
    """image (+ optional reference) -> video. Runway ``rw-generate-video`` analog."""

    spec = SkillSpec(
        id="generate_video",
        description=(
            "Animate an image into a short video clip (image-to-video), optionally "
            "conditioned on a reference image for character/location consistency."
        ),
        inputs=[
            PortSpec(name="image", media_type=MediaType.IMAGE, required=True),
            PortSpec(
                name="reference_image",
                media_type=MediaType.IMAGE,
                required=False,
                kind=PortKind.REFERENCE,
            ),
        ],
        outputs=[PortSpec(name="video", media_type=MediaType.VIDEO)],
        params_schema={
            "type": "object",
            "properties": {"prompt": {"type": "string"}, "duration_s": {"type": "number"}},
            "additionalProperties": False,
        },
        accepts_entities=[EntityType.CHARACTER, EntityType.LOCATION],
        cost_hint=6.0,
        latency_hint_s=30.0,
        tags=["generative", "video"],
    )

    async def run(self, inputs, params, entities, store: ArtifactStore):
        img = inputs.get("image")
        fp = _fingerprint(
            "video", img.id if img else "", str(params.get("prompt", "")), str(params.get("seed"))
        )
        artifact = store.put_bytes(
            b"FAKEVIDEO" + fp, MediaType.VIDEO, meta={"from_image": img.id if img else None}
        )
        return {"video": artifact}


class FakeTTSSkill(Skill):
    """text -> audio voiceover. Runway ``rw-generate-audio`` (TTS) analog."""

    spec = SkillSpec(
        id="generate_audio",
        description=(
            "Generate spoken audio (text-to-speech) from a line of text. Use a "
            "character's voice for a consistent narrator across a workflow."
        ),
        inputs=[
            PortSpec(name="voice", media_type=MediaType.AUDIO, required=False, kind=PortKind.REFERENCE),
        ],
        outputs=[PortSpec(name="audio", media_type=MediaType.AUDIO)],
        params_schema={
            "type": "object",
            "properties": {"text": {"type": "string"}, "voice_id": {"type": ["string", "null"]}},
            "required": ["text"],
            "additionalProperties": False,
        },
        accepts_entities=[EntityType.CHARACTER],
        cost_hint=1.0,
        latency_hint_s=5.0,
        tags=["generative", "audio", "tts"],
    )

    async def run(self, inputs, params, entities, store: ArtifactStore):
        voice = inputs.get("voice")
        fp = _fingerprint(
            "audio", str(params.get("text", "")),
            voice.id if voice else str(params.get("voice_id", "")), str(params.get("seed")),
        )
        artifact = store.put_bytes(b"FAKEAUDIO" + fp, MediaType.AUDIO, meta={"text": params.get("text")})
        return {"audio": artifact}


class FakeStitchSkill(Skill):
    """video + audio -> muxed video. ffmpeg-backed in production."""

    spec = SkillSpec(
        id="stitch",
        description="Combine a video track and an audio track into a final video.",
        inputs=[
            PortSpec(name="video", media_type=MediaType.VIDEO, required=True),
            PortSpec(name="audio", media_type=MediaType.AUDIO, required=True),
        ],
        outputs=[PortSpec(name="video", media_type=MediaType.VIDEO)],
        params_schema={"type": "object", "properties": {}, "additionalProperties": False},
        cost_hint=0.5,
        latency_hint_s=3.0,
        tags=["edit", "video"],
    )

    async def run(self, inputs, params, entities, store: ArtifactStore):
        v = inputs["video"]
        a = inputs["audio"]
        seed = _fingerprint("stitch", v.id, a.id)
        artifact = store.put_bytes(
            b"FAKESTITCH" + seed, MediaType.VIDEO, meta={"video": v.id, "audio": a.id}
        )
        return {"video": artifact}
