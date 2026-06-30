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
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import config
from .api import router as runs_router
from .entities import Character, Location
from .models import EntityType, Goal
from .planner.base import PlanValidationError
from .service import make_plan, run_goal
from .state import ENTITIES, REGISTRY, RUNS, STORE

app = FastAPI(title="rockbox-orchestrator", version="0.1.0")

# Allow the Vite dev server to call the API directly during development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=False,
)


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


# -- streaming run API (POST /runs, SSE events, HITL respond, uploads) -----
app.include_router(runs_router)


# -- built Studio SPA (prod) ----------------------------------------------
# Mount LAST so the catch-all does not shadow the API routes above.
_DIST = os.path.join(os.path.dirname(__file__), "..", "studio", "dist")
if os.path.isdir(_DIST):
    app.mount("/", StaticFiles(directory=_DIST, html=True), name="studio")
