from orchestrator.models import EntityType, MediaType
from orchestrator.skills.loader import parse_skill_md, spec_from_frontmatter


def test_registry_catalog_and_producers(registry):
    ids = set(registry.ids())
    assert {"generate_image", "generate_video", "generate_audio", "stitch"} <= ids
    assert [s.id for s in registry.producers_of(MediaType.IMAGE)] == ["generate_image"]
    video_producers = {s.id for s in registry.producers_of(MediaType.VIDEO)}
    assert {"generate_video", "stitch"} <= video_producers


def test_producers_sorted_by_cost(registry):
    producers = registry.producers_of(MediaType.VIDEO)
    costs = [p.cost_hint for p in producers]
    assert costs == sorted(costs)


def test_parse_skill_md_runway_frontmatter():
    text = (
        "---\n"
        "name: rw-generate-image\n"
        "description: Generate images via the Runway API.\n"
        "user-invocable: true\n"
        "allowed-tools: Read, Write, Bash(uv run *)\n"
        "---\n"
        "# Body\nRun: uv run scripts/generate_image.py\n"
    )
    md = parse_skill_md(text)
    assert md.name == "rw-generate-image"
    assert "Runway" in md.description
    assert md.frontmatter["user-invocable"] is True
    assert "Body" in md.body


def test_spec_from_typed_frontmatter():
    fm = {
        "id": "caption",
        "description": "Caption an image.",
        "inputs": [{"name": "image", "media_type": "image"}],
        "outputs": [{"name": "text", "media_type": "text"}],
        "accepts_entities": ["character"],
        "params_schema": {"type": "object", "properties": {}},
    }
    spec = spec_from_frontmatter(fm)
    assert spec.id == "caption"
    assert spec.inputs[0].media_type == MediaType.IMAGE
    assert spec.outputs[0].media_type == MediaType.TEXT
    assert spec.accepts_entities == [EntityType.CHARACTER]
