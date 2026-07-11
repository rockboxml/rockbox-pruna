# RockBox Orchestrator

A **goal-driven media-production orchestrator**. You give it a natural-language
goal plus a cast of Characters and Locations; it resolves each entity to a
consistency baseline, an LLM planner composes a typed DAG of composable agent
skills, and an executor runs it — threading the same entity baselines through
every step so a character looks and sounds the same, and a location stays
coherent, across image, video, and audio.

It is the planning/composition layer that replaces a hard-coded, linear pipeline
with one that **dynamically assembles workflows** — the power of Runway-style
workflows without node-based editing.

## Design documents

- [`docs/goal-driven-workflow-spec.md`](../docs/goal-driven-workflow-spec.md) — the normative, language-agnostic specification of the architecture (contracts, invariants, and spec-driven acceptance criteria), for reimplementing or conformance-testing the model.
- [`docs/architecture-guide.md`](../docs/architecture-guide.md) — a prose guide to the methodology, its novel aspects, its divergence from linear pipelines, and how to apply it to extend a linear framework such as OpenMontage.

## How it works

```
Goal + cast ─▶ casting ─▶ plan ─▶ bind ─▶ validate ─▶ execute ─▶ artifacts
              (baselines)  (DAG)  (cast    (typed-DAG  (waves,
                                  threaded) checks)     retries)
```

- **Skills** are the unit of extensibility, modeled on `runwayml/skills`. Each
  declares a typed IO contract (`SkillSpec`: typed input/output ports, a params
  schema, `accepts_entities`). Adding one is a single file + one registration
  line; the planner discovers it automatically. See `skills/`.
- **Characters & Locations** are first-class entities (`entities.py`). Casting
  resolves each to baseline reference artifacts (a canonical portrait, a voice,
  an establishing shot), cached for reuse across goals (a "series bible"). The
  binder threads those baselines into every relevant step for continuity.
- **Planner** — an LLM planner (`claude-opus-4-8`, adaptive thinking, structured
  outputs) proposes a DAG; a deterministic heuristic planner is the offline
  default and fallback. Either output is type-checked by `planner/validate.py`
  before execution ("the LLM proposes, the validator disposes").
- **Executor** runs the DAG in dependency waves with parallel branches, retries,
  and runtime type checks.

## Skills

| Skill | In → Out | Backend |
| --- | --- | --- |
| `generate_image` | (ref image?) → image | Pruna `server.py` (`PRUNA_URL`) / Runway `gen4_image` / fake |
| `generate_video` | image (+ref) → video | Runway / fake |
| `generate_audio` | (voice?) → audio | Runway TTS / fake |
| `stitch` | video + audio → video | ffmpeg / fake |

When no real backend is configured for a modality, a no-network fake fills in so
workflows still compose and run on a laptop / in CI.

## Run it

```bash
pip install -r orchestrator/requirements.txt
# Offline (fakes + heuristic planner):
PLANNER_MODE=heuristic uvicorn orchestrator.app:app --port 8001

# Create a reusable cast
curl -s localhost:8001/characters -H 'content-type: application/json' -d '{
  "id":"maya","name":"Maya","appearance":"short black hair, red bomber jacket",
  "style":"cinematic neon","voice":{"description":"warm alto","voice_id":"vx_maya"}}'
curl -s localhost:8001/locations -H 'content-type: application/json' -d '{
  "id":"apt","name":"Neon Apartment","appearance":"small apartment lit by neon signs"}'

# Plan + execute a goal
curl -s localhost:8001/goal -H 'content-type: application/json' -d '{
  "text":"a 5s video clip of Maya giving a tour of her neon apartment with voiceover",
  "cast":[{"entity_id":"maya"},{"entity_id":"apt"}]}'
```

Endpoints: `GET /health`, `GET /skills`, `POST/GET /characters`,
`POST/GET /locations`, `POST /plan`, `POST /goal`, `GET /artifacts/{name}`.

## Studio — goal-driven execution UI

`studio/` (repo root) is a React + Vite + TypeScript app: enter a goal plus a cast
of Characters/Locations (with uploaded reference images) and a tone, approve the
proposed plan, then watch execution as a **live vertical timeline** of humanized
step messages with **inline human-in-the-loop approvals** (Keep / Regenerate /
elicited choices) and **expandable inline artifacts** (image, multi-image
carousel of regenerate attempts, video/audio players; each opens full-view).

It is powered by a streaming run API layered on the executor (callbacks default
off, so the batch `POST /goal` and the test suite are unaffected):

- `POST /runs` → `{run_id}` — start a run (background task: plan → approve → execute)
- `GET /runs/{id}/events` — SSE timeline (`id:`/`event:`, `lastEventId` replay, heartbeats)
- `POST /runs/{id}/respond {request_id, choice_id}` — resolve a HITL gate
- `POST /entities/{id}/upload-reference`, `POST /characters/upload` — uploaded reference images (casting then skips generation)

```bash
# dev (two terminals)
PLANNER_MODE=heuristic uvicorn orchestrator.app:app --port 8001
cd studio && npm install && npm run dev          # http://localhost:5173 (proxies to :8001)

# prod: build the SPA; FastAPI serves studio/dist at /
cd studio && npm run build
uvicorn orchestrator.app:app --port 8001         # http://localhost:8001
```

Image rendering works fully offline (fakes are valid PNGs); video/audio playback
needs a real backend (`PRUNA_URL`, or `RUNWAYML_API_SECRET` + `PUBLIC_BASE_URL`).

## Configuration

| Var | Default | Meaning |
| --- | --- | --- |
| `PRUNA_URL` | — | Pruna `server.py` base URL; unset → fake image skill |
| `PLANNER_MODE` | `auto` | `auto` \| `llm` \| `heuristic` |
| `ANTHROPIC_MODEL` | `claude-opus-4-8` | Planner model |
| `ANTHROPIC_API_KEY` | — | Enables the LLM planner (`auto` mode) |
| `RUNWAYML_API_SECRET` | — | Enables real Runway skills (else fakes) |
| `RUNWAY_SKILLS_DIR` | `orchestrator/vendor/runway-skills` | Vendored `runwayml/skills` |
| `ARTIFACT_DIR` | `/tmp/rockbox-artifacts` | Where artifact bytes are written |
| `PUBLIC_BASE_URL` | — | URL this service serves artifacts at (for remote skills) |

## Tests

```bash
pytest                 # GPU-free, no network
pytest -m runway       # opt-in real-Runway e2e (needs RUNWAYML_API_SECRET + credits)
```

See `orchestrator/vendor/README.md` for vendoring the real Runway skills.
