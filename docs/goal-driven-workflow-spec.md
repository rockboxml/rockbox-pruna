# Goal-Driven Workflow — Implementation Specification

**Status:** Normative specification for spec-driven development
**Scope:** The architectural model for a goal-driven media-production workflow engine
**Reference implementation:** `orchestrator/` in this repository

This document specifies an architecture, not a codebase. It is written so that a
team can implement the model from scratch — in any language — and verify
conformance against the acceptance criteria in §16. Requirement levels use
RFC-2119 keywords: **MUST**, **SHOULD**, **MAY**.

The one-line thesis: **a natural-language goal is compiled into a typed,
validated DAG of composable skills, which an executor runs while streaming
humanized progress and pausing for human decisions.** No pipeline is authored by
hand; the pipeline is *assembled* per goal.

---

## 1. Glossary

| Term | Definition |
|---|---|
| **Goal** | The end-user's request: free text + a cast + constraints. |
| **Skill** | A composable capability with a typed I/O contract and an executable body. |
| **SkillSpec** | The machine-readable descriptor of a skill (ports, params, entity affinity). |
| **MediaArtifact** | A typed, addressable reference to a produced/consumed media file. |
| **Entity** | A first-class world-model object (Character or Location) carrying a consistency baseline. |
| **Cast** | The set of entities in play for a goal. |
| **Plan** | A DAG of steps that achieves a goal, expressed over the skill catalog. |
| **Casting** | Resolving each cast entity to baseline reference artifacts before execution. |
| **Binding** | Threading entity baselines/descriptors into the steps that reference them. |
| **Run** | One execution of a goal, with a streamed event log and human-in-the-loop gates. |

---

## 2. Design principles (normative)

1. **Skills are the unit of extensibility.** Adding a capability MUST require only
   authoring one skill (descriptor + body) and registering it. No planner,
   validator, or executor change MAY be required to make a new skill composable.
2. **Plans are typed DAGs validated before execution.** A proposer (heuristic or
   LLM) only *suggests*; a deterministic validator MUST type-check every plan and
   reject any that is not executable. "The proposer proposes, the validator
   disposes."
3. **Entities supply cross-step consistency.** Character/Location identity MUST be
   representable once and threaded, unchanged, into every step and modality that
   references it.
4. **Artifacts are typed references, not inline blobs.** The DAG MUST pass
   lightweight typed references; bytes live in a content-addressed store.
5. **Execution is observable and interruptible.** A run MUST be able to stream
   ordered progress events and to pause for human decisions that affect the
   outcome, then resume.
6. **Degrade, don't fail.** The system MUST run end-to-end with stub backends and
   without external services (no GPU, no API keys), so the control plane is
   verifiable in isolation.

---

## 3. Media types and artifacts

```
MediaType := one of { TEXT, IMAGE, VIDEO, AUDIO }

MediaArtifact {
  id:          string        # content address (e.g. sha256 of bytes)
  media_type:  MediaType
  uri:         string        # file:// | data: | https://
  mime:        string?
  meta:        map<string,any>
  produced_by: string?       # step id, or "cast" | "goal" | "upload"
  entity_id:   string?       # set iff this artifact is an entity baseline
}
```

- Artifact `id` **MUST** be content-derived, so identical bytes deduplicate and
  identity is observable (this is how consistency is *proven*, see §16).
- The store **MUST** expose a stable relative URL for each artifact
  (`/artifacts/{id}.{ext}`) and **SHOULD** expose an absolute URL when a remote
  skill must fetch it.

---

## 4. Ports, skills, and the skill contract

```
PortKind := one of { DATA, REFERENCE, ENTITY }

PortSpec {
  name:        string
  media_type:  MediaType
  required:    bool = true
  kind:        PortKind = DATA
}

SkillSpec {
  id:               string          # unique capability id, e.g. "generate_image"
  description:      string          # natural language, fed to the LLM planner
  inputs:           PortSpec[]
  outputs:          PortSpec[]       # >= 1
  params_schema:    JSONSchema       # non-artifact parameters
  accepts_entities: EntityType[]     # which entity kinds may condition this skill
  cost_hint:        number
  latency_hint_s:   number
  tags:             string[]
}
```

- A **DATA** port is fed by an upstream output or a goal seed input.
- A **REFERENCE**/**ENTITY** port is an *optional* conditioning input the binder
  fills from the cast (this is the consistency hook). Planners **MUST NOT** be
  required to bind reference ports; the binder does.

**Skill execution contract:**

```
Skill.run(inputs:  map<port, MediaArtifact>,
          params:  map<string, any>,
          entities: Entity[],          # resolved cast members referenced by the step
          store:   ArtifactStore)
      -> map<port, MediaArtifact>       # keyed by output port name
```

- `run` **MUST** be pure with respect to the DAG: it reads its inputs/params/
  entities and writes artifacts to the store; it **MUST NOT** reach into other
  steps' state.
- `run` **MUST** return exactly the declared output ports with matching
  `media_type`.

**Skill registry** — process-global, populated by import/auto-discovery:

- `register(skill)`, `get(id)`, `has(id)`, `catalog() -> SkillSpec[]`.
- `producers_of(media_type) -> SkillSpec[]` ordered by ascending `cost_hint`
  (used by the heuristic planner's backward chaining).
- Which concrete backend implements a capability (real vs stub) **MUST** be a
  registration-time decision keyed on configuration, invisible to callers.

---

## 5. Entities — the consistency engine

```
EntityType := one of { CHARACTER, LOCATION }

Entity {
  id:         string
  name:       string
  type:       EntityType
  references: MediaArtifact[]   # resolved baselines (portrait, voice, establishing shot)
  resolved:   bool = false
}

Character : Entity { appearance: string; style: string; voice: Voice }
Location  : Entity { appearance: string; style: string }
Voice     { description: string; voice_id: string?; sample: MediaArtifact? }

EntityRef { entity_id: string }   # used in Goal.cast and WorkflowStep.entity_refs
```

- An `EntityStore` **MUST** persist entities independently of any single goal
  (a reusable "series bible"), so one character is consistent across many runs.
- Each entity **MUST** expose a `descriptors()` map (name/appearance/style/voice)
  that skills merge into prompts/params, and a `references` list of baseline
  artifacts that the binder threads into reference ports.

---

## 6. Goal, plan, and step models

```
Goal {
  text:        string
  seed_inputs: MediaArtifact[]     # user-provided inputs, addressable by index
  cast:        EntityRef[]
  constraints: map<string,any>     # e.g. target_media_type, tone, hitl policy
}

InputBinding {                     # exactly one source set
  from_step: string?               # upstream step id
  port:      string?               # upstream output port (with from_step)
  from_goal: int?                  # index into Goal.seed_inputs
}

WorkflowStep {
  id:             string
  skill_id:       string
  input_bindings: map<port, InputBinding>
  params:         map<string,any>
  entity_refs:    EntityRef[]
  rationale:      string           # human-friendly reason (drives humanized message)
}

Plan { goal: Goal; steps: WorkflowStep[]; final_step: string }
```

---

## 7. The validator (the trust boundary) — normative rules

`validate_plan(plan, registry, goal, entity_types?)` **MUST** raise on the first
violation, with a precise, human-readable message (reused to re-prompt an LLM).
It **MUST** enforce all of:

- **V1 Unique ids.** Step ids are unique.
- **V2 Known skills.** Every `step.skill_id` exists in the registry.
- **V3 Acyclicity.** The graph (edges = `input_bindings.from_step`) is acyclic and
  topologically sortable; references to unknown steps are rejected.
- **V4 Port coverage.** Every *required* input port of each step is bound; no
  binding names a port the skill does not declare.
- **V5 Type satisfaction.** For each bound port, the *source* media type equals the
  port's media type — where the source type is the upstream output port's type
  (`from_step`) or `goal.seed_inputs[from_goal].media_type` (`from_goal`).
- **V6 Params.** `step.params` validate against the skill's `params_schema`
  (required keys present; unknown keys rejected when `additionalProperties:false`;
  primitive types match).
- **V7 Cast membership.** Every `entity_refs` id appears in `goal.cast`.
- **V8 Entity affinity.** When entity types are known, a step's skill
  `accepts_entities` the referenced entity's type.
- **V9 Terminal.** `final_step` exists and, when `constraints.target_media_type`
  is set, its skill produces that media type.

Rationale: a JSON schema can constrain a plan's *shape* but not cross-port type
compatibility, param validity, or entity legality. These are runtime facts and
**MUST** be checked here, so that any plan passing validation is safe to execute.

---

## 8. Casting — baseline resolution

`resolve_entity(entity, registry, store, force=false)`:

- If `entity.resolved` and not `force`: return unchanged (idempotent cache).
- If the entity already has a visual reference (e.g. an **uploaded** baseline),
  it **MUST** be used and generation **MUST** be skipped.
- Otherwise, generate a canonical baseline via the image skill from the entity's
  descriptors, tag the artifact with `entity_id` and `produced_by="cast"`, and
  append it to `references`.
- Set `resolved = true`.

Casting **MUST** run before planning-dependent binding so baselines exist to be
threaded. Baselines **MUST** be cached on the entity for reuse across runs.

---

## 9. Binding — continuity threading

`bind_plan(plan, goal, entity_store, registry) -> map<entity_id, EntityType>`
mutates the plan/goal in place and returns the entity-type map for V8. It **MUST**:

- **B1 Default continuity.** For any step whose skill `accepts_entities` and which
  has no explicit `entity_refs`, bind every accepted cast member. (The planner
  never has to remember to thread the cast.)
- **B2 Reference injection.** For an unbound `REFERENCE` IMAGE port, bind a
  referenced entity's visual baseline (added to `goal.seed_inputs`, referenced via
  `from_goal`), making the consistency link explicit *and validatable*.
- **B3 Param conditioning.** Fold entity handles into params where the skill
  expects them (e.g. a character's `voice_id` into an audio step).

The *same* baseline artifact id **MUST** be threaded into every step referencing
the same entity — this is what makes continuity observable (§16, C-CONSISTENCY).

---

## 10. Planner — one protocol, two implementations, one validator

```
Planner.plan(goal, catalog) -> Plan
```

- **Heuristic planner (deterministic).** Backward-chains from the target media
   type (from `constraints.target_media_type`, else keyword-inferred) using
   `producers_of`. It **MUST** be dependency-free and offline, and serves as the
   default and as the LLM fallback.
- **LLM planner.** Prompts a model with the goal, the catalog (`SkillSpec[]`), and
   the cast descriptors; receives a structured `Plan` draft; attaches the
   *server-side* goal (never trusting the model's echo); validates; on failure
   re-prompts with the exact validator message up to a bounded number of repair
   rounds; on exhaustion or API error **MUST** fall back to the heuristic planner.
- The plan JSON contract **SHOULD** be the plan model's own schema (single source
   of truth), and **MUST** be non-recursive if the model API restricts recursion.

Both planners' output passes through the *same* validator (§7) before execution.

---

## 11. Executor

`execute(plan, registry, store, entity_store, *, on_event?, hitl?, hitl_policy="off")`:

- **E1 Waves.** Compute a topological order and group steps into dependency
  "waves"; steps in a wave run concurrently under a concurrency limit.
- **E2 Input resolution.** Resolve each step's inputs from upstream outputs or
  goal seed inputs, and **re-check** the resolved artifact's media type against the
  port at runtime (defence in depth beyond static validation).
- **E3 Retries.** Retry a failing skill with exponential backoff up to a limit.
- **E4 Partial failure.** A terminally failed step marks its downstream dependents
  `skipped`; independent branches continue. `ok` is true iff `final_step`
  produced output.
- **E5 Backward compatibility.** With `on_event` and `hitl` unset, the executor
  **MUST** behave exactly as a plain batch executor (no events, no pauses). This
  keeps streaming/HITL strictly additive.

---

## 12. Streaming event model

```
EventType := run.started | plan.proposed
           | step.started | step.message | step.artifact | step.completed
           | hitl.requested | hitl.resolved
           | run.completed | run.error

Event {
  seq:      int          # per-run, strictly monotonic
  run_id:   string
  type:     EventType
  ts:       number
  step_id, skill_id, message, status: string?
  artifact: object?      # artifact payload + browser url
  request_id, prompt:    string?
  choices:  Choice[]
  plan:     object?      # humanized plan preview (plan.proposed)
  data:     map<string,any>
}
```

- Each event **MUST** carry a strictly monotonic per-run `seq`.
- The run **MUST** buffer all events and support replay: a subscriber joining with
  a `last_seq` receives exactly the events with `seq > last_seq`. Sequence
  increment, buffer append, and subscriber fan-out **MUST** be atomic with respect
  to subscription (register-before-snapshot), and clients **SHOULD** dedupe by
  `seq` to absorb reconnect overlap.
- `step.artifact` **MUST** carry the full attempt history for its port, so a UI can
  render a carousel when regeneration produced multiple attempts.

---

## 13. Human-in-the-loop (HITL)

```
Choice        { id: string; label: string; kind: string }  # keep|regenerate|approve|cancel|generic
HitlRequest   { request_id; step_id; skill_id; kind; prompt; choices: Choice[]; artifact? }
HitlDecision  { request_id; choice_id; notes? }
```

- HITL **MUST** be a runtime pause/resume primitive: the executor raises a
  `HitlRequest`; the run emits `hitl.requested` and blocks on a future; a
  `respond(request_id, choice_id)` call resolves it; the run emits `hitl.resolved`
  and continues.
- Policies via `constraints.hitl`:
  - `per_artifact` (default): pause after each artifact-producing step for
    **Keep** / **Regenerate**. Under this policy the executor **MUST** serialize
    (concurrency = 1) so approvals are unambiguous and ordered.
  - `final`: pause only at the deliverable.
  - `off`: never pause.
- **Regenerate** re-runs the skill with a varied nonce/seed (so content-addressed
  backends produce *different* bytes), appends the new artifact to the port's
  attempt history, and re-emits `step.artifact` (→ carousel).
- A **plan-approval** gate (Approve / Cancel) **SHOULD** precede execution, driven
  by the same HITL mechanism over a humanized plan preview.
- `respond` on an already-resolved or unknown request **MUST** be rejected
  (idempotency / double-submit safety). Disconnects **MUST NOT** leak blocked
  coroutines (cancel pending futures with the run).

---

## 14. Run lifecycle

```
RunStatus := planning -> awaiting_plan -> running <-> waiting -> (completed | cancelled | error)
```

A `RunManager.create(goal)` **MUST** spawn a background driver that:
`plan → emit plan.proposed → await plan-approval → execute(with streaming+HITL)
→ emit run.completed`, translating any failure into `run.error`. The manager
owns run sessions; each session owns its event buffer, subscribers, and pending
HITL futures.

---

## 15. HTTP surface (reference contract)

| Method | Path | Contract |
|---|---|---|
| GET | `/health` | liveness + active planner/skills |
| GET | `/skills` | the `SkillSpec[]` catalog |
| POST/GET | `/characters`, `/locations` | entity CRUD (series bible) |
| POST | `/characters/upload`, `/entities/{id}/upload-reference` | multipart; uploaded image becomes the baseline (casting then skips generation) |
| POST | `/plan` | Goal → validated Plan (no execution) |
| POST | `/goal` | Goal → ExecutionResult (batch; no streaming) |
| POST | `/runs` | Goal → `{run_id}` (starts a streamed run) |
| GET | `/runs/{id}/events` | SSE stream (`id:` = seq; `lastEventId` replay; heartbeats) |
| POST | `/runs/{id}/respond` | resolve a HITL gate |
| GET | `/artifacts/{id}.{ext}` | serve artifact bytes |

---

## 16. Acceptance criteria (spec-driven verification)

Each requirement maps to an executable, offline (no GPU/network) test. An
implementation is conformant when all pass with stub skills.

| Id | Requirement | Acceptance criterion |
|---|---|---|
| A-REGISTRY | §4 | Registering skills exposes them via `catalog`; `producers_of(t)` returns type-`t` producers ordered by cost. |
| A-VALIDATE | §7 V1–V9 | A well-typed linear and a branched plan validate; each of unknown-skill, cycle, type-mismatch, missing-required-port, bad-params, entity-not-in-cast, wrong-entity-affinity, missing-final-step is rejected with a precise message. |
| A-CASTING | §8 | An entity resolves to a baseline once and is cached on re-run; an uploaded reference is used and generation is skipped. |
| A-BINDING | §9 | The same entity's baseline is bound into image, video, and audio steps that reference it; a character's `voice_id` reaches its audio step. |
| A-HEURISTIC | §10 | "portrait" → 1 image step; "video with narration" → image→video, audio, stitch — all passing the validator. |
| A-LLM | §10 | With a stubbed model: valid-first, invalid-then-valid (one repair), and always-invalid→heuristic-fallback all yield a valid plan. |
| A-EXEC | §11 | A branched DAG runs parallel branches, threads artifacts, retries a flaky skill, and skips only the failed branch's descendants. |
| A-COMPAT | §11 E5 | `execute` with no callbacks yields byte-identical results to the pre-streaming batch behavior (the pre-existing suite stays green). |
| A-EVENTS | §12 | Event `seq` is strictly monotonic; `subscribe(last_seq)` replays only newer events. |
| A-HITL | §13 | Regenerate-then-keep causes exactly one extra `run` and a 2-attempt carousel; plan-cancel ends the run `cancelled` with no steps started; a second `respond` on a request returns false. |
| C-CONSISTENCY | §5/§9 | Two goals referencing the same character cite the **same** resolved baseline artifact id — consistency is observable in the results, not asserted by inspection. |

---

## 17. Extension recipes

- **Add a skill.** Author a descriptor (typed ports, params schema,
  `accepts_entities`) + a `run` body; register it. The planner discovers it, the
  validator type-checks it, the binder threads the cast through its reference
  ports — no engine change.
- **Add a modality.** Introduce the `MediaType`, then one producer skill for it;
  the heuristic planner's `producers_of` and the LLM catalog pick it up.
- **Add an entity type.** Extend `EntityType`, give it descriptors and a baseline
  resolver, and declare which skills `accepts_entities` it.
- **Swap a backend.** Bind the capability id to a different implementation at
  registration time (config-keyed); callers, planner, validator, and executor are
  unchanged.
```
