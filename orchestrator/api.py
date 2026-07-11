"""
Streaming run API + reference-image uploads for the execution UI.

Endpoints (mounted by ``app.py``):
- ``POST /runs``                       — start a run, returns ``{run_id}``
- ``GET  /runs/{id}/events``           — SSE event stream (seq id + replay)
- ``POST /runs/{id}/respond``          — resolve a HITL request (approve / keep / …)
- ``POST /entities/{id}/upload-reference`` — attach an uploaded baseline image
- ``POST /characters/upload``          — create a Character/Location with an optional image
"""

from __future__ import annotations

import asyncio
import uuid

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .entities import Character, Location
from .events import Event, EventType
from .models import EntityType, Goal, MediaType
from .state import ENTITIES, RUNS, STORE

router = APIRouter()

_TERMINAL = {EventType.RUN_COMPLETED, EventType.RUN_ERROR}


@router.post("/runs")
async def create_run(goal: Goal) -> dict:
    sess = RUNS.create(goal)
    return {"run_id": sess.run_id}


@router.get("/runs/{run_id}/events")
async def run_events(run_id: str, request: Request) -> StreamingResponse:
    sess = RUNS.get(run_id)
    if sess is None:
        raise HTTPException(status_code=404, detail="unknown run")

    last_seq = _last_event_id(request)
    queue, backlog = await sess.subscribe(last_seq)

    async def gen():
        try:
            for ev in backlog:
                yield _sse(ev)
            while True:
                if await request.is_disconnected():
                    break
                try:
                    ev = await asyncio.wait_for(queue.get(), timeout=15.0)
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
                    continue
                yield _sse(ev)
                if ev.type in _TERMINAL:
                    break
        finally:
            sess.unsubscribe(queue)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


class RespondBody(BaseModel):
    request_id: str
    choice_id: str
    notes: str | None = None


@router.post("/runs/{run_id}/respond")
async def respond(run_id: str, body: RespondBody) -> dict:
    sess = RUNS.get(run_id)
    if sess is None:
        raise HTTPException(status_code=404, detail="unknown run")
    if not sess.resolve(body.request_id, body.choice_id, body.notes):
        raise HTTPException(status_code=409, detail="no pending request with that id")
    return {"ok": True}


@router.post("/entities/{entity_id}/upload-reference")
async def upload_reference(entity_id: str, file: UploadFile = File(...)) -> dict:
    if not ENTITIES.has(entity_id):
        raise HTTPException(status_code=404, detail="unknown entity")
    entity = ENTITIES.get(entity_id)
    data = await file.read()
    art = STORE.put_bytes(
        data, MediaType.IMAGE, mime=file.content_type or "image/png",
        produced_by="upload", entity_id=entity_id,
    )
    entity.references.append(art)  # casting.resolve_entity now skips generation
    ENTITIES.put(entity)
    return {"entity_id": entity_id, "artifact": STORE.payload(art)}


@router.post("/characters/upload")
async def create_character_with_reference(
    name: str = Form(...),
    appearance: str = Form(""),
    style: str = Form(""),
    type: str = Form("character"),
    voice_id: str = Form(""),
    file: UploadFile | None = File(None),
) -> dict:
    etype = EntityType(type)
    entity_id = uuid.uuid4().hex
    if etype == EntityType.CHARACTER:
        ent = Character(id=entity_id, name=name, appearance=appearance, style=style)
        if voice_id:
            ent.voice.voice_id = voice_id
    else:
        ent = Location(id=entity_id, name=name, appearance=appearance, style=style)
    ENTITIES.put(ent)
    if file is not None:
        data = await file.read()
        art = STORE.put_bytes(
            data, MediaType.IMAGE, mime=file.content_type or "image/png",
            produced_by="upload", entity_id=entity_id,
        )
        ent.references.append(art)
        ENTITIES.put(ent)
    return ent.model_dump()


def _sse(ev: Event) -> str:
    return f"id: {ev.seq}\nevent: {ev.type.value}\ndata: {ev.model_dump_json()}\n\n"


def _last_event_id(request: Request) -> int | None:
    raw = request.headers.get("Last-Event-ID") or request.query_params.get("lastEventId")
    if raw and raw.isdigit():
        return int(raw)
    return None
