"""
FastAPI surface for the orchestrator.

Separate service from ``server.py`` (the Pruna image model), which it drives over
HTTP via ``PRUNA_URL``. Endpoints:

- ``GET  /health``            — liveness + which planner/skills are active
- ``GET  /skills``            — the skill catalog the planner reasons over
- ``POST /characters`` / ``GET /characters`` — manage the reusable cast
- ``POST /locations``  / ``GET /locations``
- ``POST /plan``              — Goal -> Plan (plan only)
- ``POST /goal``              — Goal -> ExecutionResult (plan + execute)
- ``GET  /artifacts/{name}``  — serve produced bytes (so remote skills can fetch)
"""

from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from . import config
from .artifacts import ArtifactStore
from .entities import Character, EntityStore, Location, make_entity
from .models import EntityType, Goal
from .planner.base import PlanValidationError
from .service import get_planner, make_plan, run_goal
from .skills import REGISTRY

app = FastAPI(title="rockbox-orchestrator", version="0.1.0")

STORE = ArtifactStore()
ENTITIES = EntityStore()


@app.get("/health")
def health() -> dict:
    return {
        "ok": True,
        "planner": "llm" if config.use_llm_planner() else "heuristic",
        "pruna_url": config.PRUNA_URL,
        "skills": sorted(REGISTRY.ids()),
        "characters": len(ENTITIES.of_type(EntityType.CHARACTER)),
        "locations": len(ENTITIES.of_type(EntityType.LOCATION)),
    }


@app.get("/skills")
def skills() -> list[dict]:
    return [spec.model_dump() for spec in REGISTRY.catalog()]


# -- entity CRUD ----------------------------------------------------------
@app.post("/characters")
def create_character(body: Character) -> dict:
    body.type = EntityType.CHARACTER
    return ENTITIES.put(body).model_dump()


@app.get("/characters")
def list_characters() -> list[dict]:
    return [e.model_dump() for e in ENTITIES.of_type(EntityType.CHARACTER)]


@app.post("/locations")
def create_location(body: Location) -> dict:
    body.type = EntityType.LOCATION
    return ENTITIES.put(body).model_dump()


@app.get("/locations")
def list_locations() -> list[dict]:
    return [e.model_dump() for e in ENTITIES.of_type(EntityType.LOCATION)]


# -- planning / execution -------------------------------------------------
@app.post("/plan")
async def plan_endpoint(goal: Goal) -> dict:
    try:
        plan = await make_plan(goal, REGISTRY, STORE, ENTITIES)
    except PlanValidationError as exc:
        raise HTTPException(status_code=422, detail=f"plan invalid: {exc}") from exc
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return plan.model_dump()


@app.post("/goal")
async def goal_endpoint(goal: Goal) -> dict:
    try:
        result = await run_goal(goal, REGISTRY, STORE, ENTITIES)
    except PlanValidationError as exc:
        raise HTTPException(status_code=422, detail=f"plan invalid: {exc}") from exc
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result.model_dump()


# -- artifact serving (for remote skills like Runway) ---------------------
@app.get("/artifacts/{name}")
def get_artifact(name: str) -> FileResponse:
    # name is "<sha>.<ext>"; confine to the artifact dir (no traversal).
    safe = os.path.basename(name)
    path = os.path.join(STORE.root, safe)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="artifact not found")
    return FileResponse(path)
