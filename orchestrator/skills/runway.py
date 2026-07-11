"""
Runway skill adapter.

Wraps the vendored ``runwayml/skills`` (a git submodule under
``vendor/runway-skills``) so the planner can compose real Runway capabilities.
Each real skill ships a runnable ``scripts/*.py`` invoked as ``uv run …`` and
authed via ``RUNWAYML_API_SECRET``; this adapter declares the typed
:class:`SkillSpec` (which the planner reasons over) and translates the bound cast
into Runway's reference-image / voice flags so a character/location stays
on-model across modalities.

The reference-image mapping is the verified consistency hook: ``rw-generate-image``
accepts ``--reference-images <tag>=<URL>`` (lowercase 3–16-char tag, max 3) on
``gen4_image`` — so **tag = entity name, URL = the entity's resolved baseline
artifact**. The video/audio flag builders are best-effort and should be
reconciled against the vendored scripts' actual CLIs at integration time.
"""

from __future__ import annotations

import asyncio
import os
import re
import tempfile

from .. import config
from ..artifacts import ArtifactStore
from ..entities import Character, Entity
from ..models import (
    EntityType,
    MediaArtifact,
    MediaType,
    PortKind,
    PortSpec,
    SkillSpec,
)
from .base import Skill
from .generate_image import build_prompt
from .loader import load_skill_md

MAX_REFERENCE_IMAGES = 3  # Runway gen4_image limit


def sanitize_tag(name: str) -> str:
    """Runway reference tags must be lowercase, 3–16 chars, alphanumeric."""
    tag = re.sub(r"[^a-z0-9]", "", name.lower())
    if len(tag) < 3:
        tag = (tag + "ref")[:3]
    return tag[:16]


def reference_image_args(
    entities: list[Entity],
    store: ArtifactStore,
    *,
    max_refs: int = MAX_REFERENCE_IMAGES,
) -> list[str]:
    """Build ``tag=URL`` reference-image args from entities' visual baselines.

    Caps at ``max_refs`` (logging the drop) and de-dups tags.
    """
    args: list[str] = []
    seen: set[str] = set()
    for entity in entities:
        baseline = next(
            (r for r in entity.references if r.media_type == MediaType.IMAGE), None
        )
        if baseline is None:
            continue
        tag = sanitize_tag(entity.name or entity.id)
        if tag in seen:
            continue
        if len(args) >= max_refs:
            import logging

            logging.getLogger(__name__).warning(
                "dropping reference image for '%s' (Runway max %d reached)",
                entity.name,
                max_refs,
            )
            break
        seen.add(tag)
        args.append(f"{tag}={store.public_url(baseline)}")
    return args


class RunwaySkill(Skill):
    """A skill backed by a vendored runway ``scripts/*.py`` invoked via ``uv run``."""

    def __init__(
        self,
        spec: SkillSpec,
        script_path: str,
        *,
        output_port: str,
        output_media: MediaType,
        kind: str,
    ):
        self.spec = spec
        self.script_path = script_path
        self.output_port = output_port
        self.output_media = output_media
        self.kind = kind  # "image" | "video" | "audio"

    def build_argv(self, inputs, params, entities, store, out_path: str) -> list[str]:
        argv = ["uv", "run", self.script_path]
        if self.kind == "image":
            argv += ["--prompt", build_prompt(params, entities)]
            argv += ["--filename", out_path]
            if params.get("model"):
                argv += ["--model", str(params["model"])]
            refs = reference_image_args(entities, store)
            for ref in refs:
                argv += ["--reference-images", ref]
        elif self.kind == "video":
            img = inputs.get("image")
            if img is not None:
                argv += ["--image", store.public_url(img)]
            argv += ["--prompt", build_prompt(params, entities)]
            argv += ["--filename", out_path]
            for ref in reference_image_args(entities, store):
                argv += ["--reference-images", ref]
        elif self.kind == "audio":
            argv += ["--text", str(params.get("text", ""))]
            voice_id = params.get("voice_id") or _voice_id(entities)
            if voice_id:
                argv += ["--voice", str(voice_id)]
            argv += ["--filename", out_path]
        return argv

    async def run(self, inputs, params, entities, store: ArtifactStore):
        ext = {"image": "png", "video": "mp4", "audio": "mp3"}[self.kind]
        fd, out_path = tempfile.mkstemp(suffix=f".{ext}")
        os.close(fd)
        argv = self.build_argv(inputs, params, entities, store, out_path)

        env = dict(os.environ)  # RUNWAYML_API_SECRET is read from env by the script
        proc = await asyncio.create_subprocess_exec(
            *argv,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(
                f"runway skill '{self.spec.id}' failed ({proc.returncode}): "
                f"{stderr.decode(errors='replace')[:500]}"
            )

        # Scripts write the file and print its path; prefer the file we asked for.
        path = out_path if os.path.exists(out_path) else _last_path(stdout)
        with open(path, "rb") as fh:
            data = fh.read()
        artifact = store.put_bytes(data, self.output_media)
        return {self.output_port: artifact}


def _voice_id(entities: list[Entity]) -> str | None:
    for e in entities:
        if isinstance(e, Character) and e.voice.voice_id:
            return e.voice.voice_id
    return None


def _last_path(stdout: bytes) -> str:
    line = stdout.decode(errors="replace").strip().splitlines()[-1] if stdout.strip() else ""
    return line.strip()


# -- registration ---------------------------------------------------------
def _image_spec() -> SkillSpec:
    return SkillSpec(
        id="generate_image",
        description="Generate an image with Runway gen4_image, optionally conditioned on reference images for character/location consistency.",
        inputs=[PortSpec(name="reference_image", media_type=MediaType.IMAGE, required=False, kind=PortKind.REFERENCE)],
        outputs=[PortSpec(name="image", media_type=MediaType.IMAGE)],
        params_schema={
            "type": "object",
            "properties": {"prompt": {"type": "string"}, "model": {"type": "string"}, "ratio": {"type": "string"}},
            "required": ["prompt"],
            "additionalProperties": False,
        },
        accepts_entities=[EntityType.CHARACTER, EntityType.LOCATION],
        cost_hint=4.0,
        latency_hint_s=15.0,
        tags=["generative", "image", "runway"],
    )


def _video_spec() -> SkillSpec:
    return SkillSpec(
        id="generate_video",
        description="Generate a video with Runway (image-to-video / text-to-video), conditioned on reference images for consistency.",
        inputs=[
            PortSpec(name="image", media_type=MediaType.IMAGE, required=True),
            PortSpec(name="reference_image", media_type=MediaType.IMAGE, required=False, kind=PortKind.REFERENCE),
        ],
        outputs=[PortSpec(name="video", media_type=MediaType.VIDEO)],
        params_schema={
            "type": "object",
            "properties": {"prompt": {"type": "string"}, "model": {"type": "string"}, "duration_s": {"type": "number"}},
            "additionalProperties": False,
        },
        accepts_entities=[EntityType.CHARACTER, EntityType.LOCATION],
        cost_hint=8.0,
        latency_hint_s=40.0,
        tags=["generative", "video", "runway"],
    )


def _audio_spec() -> SkillSpec:
    return SkillSpec(
        id="generate_audio",
        description="Generate spoken audio with Runway (TTS), using a character's voice for a consistent narrator.",
        inputs=[PortSpec(name="voice", media_type=MediaType.AUDIO, required=False, kind=PortKind.REFERENCE)],
        outputs=[PortSpec(name="audio", media_type=MediaType.AUDIO)],
        params_schema={
            "type": "object",
            "properties": {"text": {"type": "string"}, "voice_id": {"type": ["string", "null"]}},
            "required": ["text"],
            "additionalProperties": False,
        },
        accepts_entities=[EntityType.CHARACTER],
        cost_hint=1.5,
        latency_hint_s=6.0,
        tags=["generative", "audio", "runway"],
    )


_SKILL_DEFS = [
    ("rw-generate-image", "generate_image.py", _image_spec, "image", "image", MediaType.IMAGE),
    ("rw-generate-video", "generate_video.py", _video_spec, "video", "video", MediaType.VIDEO),
    ("rw-generate-audio", "generate_audio.py", _audio_spec, "audio", "audio", MediaType.AUDIO),
]


def register_runway_skills(registry, skills_dir: str | None = None) -> bool:
    """Register Runway-backed skills found in the vendored skills dir.

    Returns True if at least one was registered (so the fakes are skipped).
    """
    root = skills_dir or config.RUNWAY_SKILLS_DIR
    registered = False
    for folder, script_name, spec_fn, kind, out_port, out_media in _SKILL_DEFS:
        script_path = os.path.join(root, "skills", folder, "scripts", script_name)
        if not os.path.isfile(script_path):
            continue
        # Cross-check the vendored SKILL.md name for discovery/sanity.
        md_path = os.path.join(root, "skills", folder, "SKILL.md")
        if os.path.isfile(md_path):
            _ = load_skill_md(md_path)
        registry.register(
            RunwaySkill(
                spec_fn(),
                script_path,
                output_port=out_port,
                output_media=out_media,
                kind=kind,
            )
        )
        registered = True
    return registered
