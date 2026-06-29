"""
Parse ``runwayml/skills``-style ``SKILL.md`` files.

A SKILL.md begins with a YAML frontmatter block delimited by ``---`` lines,
followed by Markdown instructions. Real Runway frontmatter carries
``name``/``description``/``user-invocable``/``allowed-tools``; our own skills may
add the typed contract (``inputs``/``outputs``/``params_schema``/
``accepts_entities``) so a full :class:`SkillSpec` can be built directly.

The loader is intentionally dependency-light: it parses the frontmatter and,
when the typed fields are present, returns a :class:`SkillSpec`. The Runway
adapter uses :func:`parse_skill_md` to get name/description for discovery while
declaring its typed contract in code.
"""

from __future__ import annotations

import os

import yaml

from ..models import EntityType, PortKind, PortSpec, SkillSpec


class SkillMd:
    """A parsed SKILL.md: frontmatter dict + Markdown body."""

    def __init__(self, frontmatter: dict, body: str, path: str | None = None):
        self.frontmatter = frontmatter
        self.body = body
        self.path = path

    @property
    def name(self) -> str:
        return self.frontmatter.get("name", "")

    @property
    def description(self) -> str:
        return self.frontmatter.get("description", "")


def parse_skill_md(text: str, *, path: str | None = None) -> SkillMd:
    """Split a SKILL.md string into (frontmatter, body)."""
    fm: dict = {}
    body = text
    if text.startswith("---"):
        # Strip the leading delimiter, then split on the next one.
        rest = text[3:]
        end = rest.find("\n---")
        if end != -1:
            fm_text = rest[:end]
            body = rest[end + 4 :].lstrip("\n")
            fm = yaml.safe_load(fm_text) or {}
    return SkillMd(frontmatter=fm, body=body, path=path)


def load_skill_md(path: str) -> SkillMd:
    with open(path, encoding="utf-8") as fh:
        return parse_skill_md(fh.read(), path=path)


def _ports(raw: list | None) -> list[PortSpec]:
    ports: list[PortSpec] = []
    for p in raw or []:
        ports.append(
            PortSpec(
                name=p["name"],
                media_type=p["media_type"],
                required=p.get("required", True),
                kind=PortKind(p.get("kind", PortKind.DATA)),
                description=p.get("description", ""),
            )
        )
    return ports


def spec_from_frontmatter(fm: dict) -> SkillSpec:
    """Build a SkillSpec from frontmatter that includes the typed contract.

    Raises KeyError/ValueError if the typed fields are missing or malformed — use
    this only for skills authored with the full contract (our own skills), not
    raw Runway skills.
    """
    return SkillSpec(
        id=fm["id"],
        description=fm.get("description", ""),
        inputs=_ports(fm.get("inputs")),
        outputs=_ports(fm.get("outputs")),
        params_schema=fm.get("params_schema", {}),
        accepts_entities=[EntityType(e) for e in fm.get("accepts_entities", [])],
        cost_hint=fm.get("cost_hint", 1.0),
        latency_hint_s=fm.get("latency_hint_s", 5.0),
        tags=fm.get("tags", []),
    )


def discover_skill_mds(root: str) -> list[SkillMd]:
    """Find and parse every ``SKILL.md`` under ``root`` (recursively)."""
    found: list[SkillMd] = []
    if not os.path.isdir(root):
        return found
    for dirpath, _dirnames, filenames in os.walk(root):
        for fn in filenames:
            if fn == "SKILL.md":
                found.append(load_skill_md(os.path.join(dirpath, fn)))
    return found
