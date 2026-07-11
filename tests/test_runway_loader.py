"""Runway adapter tests that need no API key — argv building and tag rules."""

from __future__ import annotations

from orchestrator.planner.casting import resolve_cast
from orchestrator.skills.runway import (
    MAX_REFERENCE_IMAGES,
    RunwaySkill,
    _image_spec,
    reference_image_args,
    sanitize_tag,
)


def test_sanitize_tag_rules():
    assert sanitize_tag("Maya") == "maya"
    assert sanitize_tag("Neon Apartment!") == "neonapartment"
    assert sanitize_tag("X") == "xre"  # padded to the 3-char minimum
    assert len(sanitize_tag("a" * 50)) == 16  # capped at 16


async def test_reference_args_from_baselines(registry, store, maya, apartment):
    await resolve_cast([maya, apartment], registry, store)
    args = reference_image_args([maya, apartment], store)
    assert len(args) == 2
    tags = [a.split("=", 1)[0] for a in args]
    assert tags == ["maya", "neonapartment"]
    assert all(a.split("=", 1)[1].startswith("https://orch.test/artifacts/") for a in args)


async def test_reference_args_capped_at_three(registry, store):
    from orchestrator.entities import Character

    chars = [
        Character(id=f"c{i}", name=f"Char{i}", appearance="x") for i in range(5)
    ]
    await resolve_cast(chars, registry, store)
    args = reference_image_args(chars, store)
    assert len(args) == MAX_REFERENCE_IMAGES


async def test_image_skill_builds_reference_image_argv(registry, store, maya, apartment):
    await resolve_cast([maya, apartment], registry, store)
    skill = RunwaySkill(
        _image_spec(),
        "/vendor/skills/rw-generate-image/scripts/generate_image.py",
        output_port="image",
        output_media=__import__(
            "orchestrator.models", fromlist=["MediaType"]
        ).MediaType.IMAGE,
        kind="image",
    )
    argv = skill.build_argv(
        inputs={},
        params={"prompt": "Maya at home", "model": "gen4_image"},
        entities=[maya, apartment],
        store=store,
        out_path="/tmp/out.png",
    )
    assert argv[:3] == ["uv", "run", skill.script_path]
    assert "--model" in argv and argv[argv.index("--model") + 1] == "gen4_image"
    refs = [argv[i + 1] for i, a in enumerate(argv) if a == "--reference-images"]
    assert any(r.startswith("maya=") for r in refs)
    assert any(r.startswith("neonapartment=") for r in refs)
