"""
RockBox goal-driven media-production orchestrator.

Turns a natural-language goal (plus a cast of Characters and Locations) into a
typed DAG of composable agent skills, executes it, and returns typed media
artifacts. Skills are modeled on Runway's agent skills; Characters and Locations
are first-class entities whose resolved baseline artifacts are threaded through
every step for cross-modal consistency.

This package is a separate service from ``server.py`` (the Pruna text-to-image
inference server), which it drives over HTTP as one backing skill.
"""

__all__ = ["__version__"]

__version__ = "0.1.0"
