"""
Process-global singletons shared by the API modules.

Kept in one place so ``app.py`` and ``api.py`` reference the same artifact store,
entity store, skill registry, and run manager without an import cycle.
"""

from __future__ import annotations

from .artifacts import ArtifactStore
from .entities import EntityStore
from .runtime import RunManager
from .skills import REGISTRY

STORE = ArtifactStore()
ENTITIES = EntityStore()
RUNS = RunManager(REGISTRY, STORE, ENTITIES)

__all__ = ["STORE", "ENTITIES", "RUNS", "REGISTRY"]
