"""
Runtime configuration, sourced from environment variables.

Kept tiny and import-safe (no network, no heavy deps at import time) so the
package can be imported in tests without any services running.
"""

from __future__ import annotations

import os


def _clean(url: str) -> str:
    return url.rstrip("/")


# URL of the Pruna text-to-image server (server.py). When unset, the
# generate_image skill falls back to the GPU-free FakeImageSkill.
PRUNA_URL: str | None = (
    _clean(os.environ["PRUNA_URL"]) if os.environ.get("PRUNA_URL") else None
)

# "llm" | "heuristic" | "auto" (default). "auto" uses the LLM planner when an
# Anthropic key is available, else the deterministic heuristic planner.
PLANNER_MODE: str = os.environ.get("PLANNER_MODE", "auto").lower()

# Where produced artifact bytes are written (content-addressed).
ARTIFACT_DIR: str = os.environ.get("ARTIFACT_DIR", "/tmp/rockbox-artifacts")

# Base URL at which this orchestrator serves artifact bytes, so remote skills
# (e.g. Runway) can fetch reference images by URL.
PUBLIC_BASE_URL: str | None = (
    _clean(os.environ["PUBLIC_BASE_URL"]) if os.environ.get("PUBLIC_BASE_URL") else None
)

# Claude model for the LLM planner.
ANTHROPIC_MODEL: str = os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-8")

# Real Runway skills auth. When unset, Runway-backed skills are not registered.
RUNWAYML_API_SECRET: str | None = os.environ.get("RUNWAYML_API_SECRET")

# Path to the vendored runwayml/skills checkout (git submodule).
RUNWAY_SKILLS_DIR: str = os.environ.get(
    "RUNWAY_SKILLS_DIR",
    os.path.join(os.path.dirname(__file__), "vendor", "runway-skills"),
)


def anthropic_available() -> bool:
    """True if an Anthropic credential is present in the environment."""
    return bool(
        os.environ.get("ANTHROPIC_API_KEY")
        or os.environ.get("ANTHROPIC_AUTH_TOKEN")
        or os.environ.get("ANTHROPIC_PROFILE")
    )


def use_llm_planner() -> bool:
    """Resolve whether to use the LLM planner given mode + credentials."""
    if PLANNER_MODE == "llm":
        return True
    if PLANNER_MODE == "heuristic":
        return False
    return anthropic_available()
