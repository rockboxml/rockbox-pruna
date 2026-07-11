# Goal-Driven Media Workflows — An Architectural Guide

## The idea in one paragraph

Most media-production automation is a **pipeline**: a fixed, ordered sequence of
stages someone designed in advance. You pick the pipeline that matches what you
want to make, and an agent walks its stages. This guide describes a different
model — **goal-driven workflow composition** — in which no pipeline is authored
by hand. Instead, an end-user states a goal, and the system *compiles* that goal
into a workflow: it selects capabilities, wires them into a typed dependency
graph, proves the graph is executable, and runs it while narrating progress and
pausing for human judgment. The pipeline is an *output* of the system, not an
input to it. This document explains the methodology, what is genuinely new about
it, why it diverges from linear flow, and — concretely — how to use it to extend
an existing linear framework such as [OpenMontage](https://github.com/calesthio/OpenMontage).

---

## 1. The methodology

The model rests on four moving parts and one discipline.

**Skills are typed capabilities.** A skill is the atomic unit of work — generate
an image, animate a frame, synthesize a voice, stitch tracks. What makes a skill
*composable* is not its code but its **contract**: a declaration of typed input
and output ports (image, video, audio, text), a schema for its parameters, and a
note about which world-model entities it can be conditioned on. The engine never
needs to understand what a skill *does*; it only reasons over contracts. This is
the lever that makes the system extensible: adding a capability is authoring one
contract-plus-body and registering it, with no change to the planner, validator,
or executor.

**Plans are validated typed DAGs.** A goal is turned into a directed acyclic graph
of steps, each step invoking a skill and binding its inputs to upstream outputs or
to user-provided seeds. Crucially, the thing that *produces* the plan is separated
from the thing that *trusts* it. A planner — heuristic or LLM — merely proposes;
a deterministic validator then type-checks the whole graph: every required input
is satisfied by an upstream output of the same media type, parameters match their
schemas, the graph is acyclic, and the final step yields the requested kind of
media. Only a plan that survives validation is executed. We summarize the
discipline as *"the proposer proposes, the validator disposes."*

**Entities carry consistency.** Characters and Locations are first-class objects,
not prompt fragments. Each is resolved once to a **baseline** — a canonical
portrait, a voice, an establishing shot — and that same baseline is threaded, by
the system rather than by the author, into every step and every modality that
references the entity. The result is continuity: the same character looks and
sounds the same across the opening image, the animated shot, and the voiceover,
because all three were conditioned on one shared, content-addressed baseline.

**Execution is a conversation.** Running the graph is not a black box that returns
a file. It is a stream of humanized events — "Sketching the opening frame…",
"Frame ready." — and, at chosen points, a **pause** that hands control back to a
person: approve the plan before it runs; keep or regenerate a shot; choose among
options. These human-in-the-loop gates are a runtime primitive: the executor
genuinely blocks on a decision and resumes with it, so the human's choice changes
what happens next, not merely what is displayed.

The discipline tying these together is **degrade, don't fail**: the entire control
plane must run with stub backends, offline, with no GPU and no API keys. Planning,
validation, binding, streaming, and HITL are all verifiable without ever calling a
real model — which is why the architecture can be tested exhaustively and cheaply.

---

## 2. What is novel here

Several of these ideas exist in isolation; their *combination*, and three specific
choices, are what distinguish this model.

- **Type-checking as the trust boundary for generated plans.** When an LLM writes
  the workflow, the interesting question is not "can it produce JSON of the right
  shape" — schemas handle that — but "is the workflow it wrote actually runnable."
  Cross-port media-type compatibility, parameter validity, and entity legality are
  runtime facts a schema cannot express. Making a deterministic validator the sole
  gate — and feeding its precise error messages back to the model as repair
  instructions — turns an unreliable generator into a reliable planner without
  trusting it. The LLM's failures become *validation errors*, not runtime crashes.

- **Cross-generation consistency as an engine feature, not a prompt trick.** Tools
  like Runway offer character references per call; what is usually missing is a
  framework that guarantees the *same* reference is used everywhere, automatically,
  across modalities. Promoting Characters and Locations to persisted entities with
  resolved baselines, and having a *binder* inject those baselines into reference
  ports across the whole DAG, makes continuity a property of the system rather than
  a responsibility of the author. Because baselines are content-addressed,
  consistency is *observable*: two runs that reference the same character can be
  shown to cite the identical baseline id.

- **The timeline and its pauses as runtime primitives.** Progress is not logging
  bolted on afterward; it is a first-class, replayable, sequence-numbered event
  stream, and the human gates are real `await` points inside the executor. This
  makes "regenerate this shot" append a new attempt to a carousel and re-run
  exactly one step — a small, precise, resumable interaction — rather than
  restarting the job.

A fourth, quieter novelty is **strict additivity**: streaming and HITL were layered
onto a batch executor through optional callbacks that default off, so the
synchronous engine and its test suite remained byte-for-byte unchanged. The
interactive system is the same engine with observers attached.

---

## 3. The divergence from linear flow

A linear framework encodes *what to do* as an ordered list of stages. Its strengths
are real: it is legible, predictable, and easy to reason about; a human designed
the sequence, so it embodies craft knowledge. Its limits are structural:

- **One shape per intent.** Every distinct kind of output needs its own authored
  pipeline. Twelve video types means twelve hand-written pipelines; the thirteenth
  is a new authoring task, not an emergent capability.
- **No inherent parallelism.** A list is sequential by construction. Independent
  work — generating a voiceover while a shot renders — must be arranged by hand, if
  at all.
- **Weak composition.** Stages are coupled to their pipeline. Reusing a capability
  in a new arrangement means editing pipelines, not adding a skill.
- **Consistency is incidental.** Nothing in a stage list guarantees that stage 3
  and stage 7 refer to the same character; that is left to prompts and vigilance.

The goal-driven model diverges by replacing the authored sequence with a
**compiled graph**. The consequences follow directly from the shape change:

| Property | Linear pipeline | Goal-driven DAG |
|---|---|---|
| Pipeline origin | Authored per output type | Assembled per goal |
| Adding a capability | Edit pipelines that use it | Register one skill |
| Concurrency | Manual, if any | Inherent (independent branches run in waves) |
| New intents | New authored pipeline | Emerge from the existing skill catalog |
| Correctness | Trust the author | Validated typed graph |
| Consistency | Incidental (prompt-level) | Structural (entity baselines threaded) |
| Human control | Stage checkpoints | Runtime pause/resume on any step |

The important reframe: linearity is not *wrong*, it is a *special case*. A
goal-driven engine can produce a straight-line plan when that is what the goal
implies; it simply is not *restricted* to straight lines, and it does not require a
human to have anticipated the line in advance.

---

## 4. Extending a linear framework: the OpenMontage case study

The most valuable use of this model is not to replace a mature linear framework but
to **wrap and enhance one**. OpenMontage is an instructive target because it is a
strong, well-factored linear system, and its factoring maps almost perfectly onto
the goal-driven model's seams.

**What OpenMontage is.** OpenMontage turns an AI coding assistant into a video
studio. Its architecture is three layers: `tools/` — dozens of Python executables
for image/video/audio generation and analysis; `skills/` — Markdown instruction
files that teach the agent how to use each tool; and `pipeline_defs/` — YAML
playbooks that define, per video type, a fixed sequence of stages
(*research → proposal → script → scene plan → assets → edit → compose*). The agent
reads a pipeline manifest and its stage-director skills and walks the stages,
checkpointing for human approval at creative decision points. It is, in the precise
sense of this guide, a **linear, per-type, instruction-driven pipeline system**.

**Where the two models meet.** Notice the correspondence:

| OpenMontage | Goal-driven model |
|---|---|
| `tools/` (executables) | Skill **bodies** (`Skill.run`) |
| `skills/` (Markdown how-to) | Skill **descriptors** — become the natural-language `description` on a typed `SkillSpec` |
| `pipeline_defs/` (YAML stage lists) | **Nothing to author** — the DAG is compiled by the planner |
| Stage checkpoints | HITL gates (plan approval, keep/regenerate, elicitation) |
| Per-type pipelines | Emergent plans over one catalog |
| (absent) | First-class Characters/Locations with threaded baselines |

The extension thesis writes itself: **keep OpenMontage's tools and skills; replace
its hand-authored pipeline manifests with a goal-driven planner.** The 500+ existing
agent skills are exactly the capability catalog a planner needs — each already has
a human-readable description and a tool it drives. Wrapping each as a typed
`SkillSpec` (adding declared input/output media types and a params schema over its
existing tool's CLI) turns the instruction library into a *composable* catalog. The
twelve authored pipelines stop being inputs and become *possible outputs*: any of
them — and arrangements no one wrote down — can be assembled from the same catalog
when a goal calls for it.

**A concrete migration path.**

1. **Adopt the artifact and skill contracts** without touching the tools. For each
   OpenMontage tool, declare a `SkillSpec`: input/output ports typed by media kind,
   a params schema mirroring the tool's flags, and `accepts_entities` where the tool
   can take a reference. The tool executable becomes the skill body.
2. **Introduce the planner and validator alongside the existing manifests.** Run
   them in "shadow": for a given brief, let the planner assemble a DAG and validate
   it, and compare against the authored pipeline. This builds confidence that the
   compiled graph is at least as good, with zero risk.
3. **Add the entity layer.** OpenMontage has no cross-generation Character/Location
   consistency framework; this is the highest-value net-new capability. Resolve a
   character once and thread its baseline through every asset stage. Continuity
   stops depending on prompt discipline.
4. **Replace stage checkpoints with runtime HITL.** OpenMontage already pauses at
   creative decision points; the goal-driven gate model generalizes this to any
   step, with choice-based options (approve the plan, keep or regenerate a specific
   asset, choose among elicited directions) that actually steer execution.
5. **Retire pipeline manifests incrementally.** As the planner covers each video
   type's intent, its YAML manifest becomes redundant. The manifests can remain as
   *priors* — seed heuristics or few-shot exemplars for the planner — rather than as
   the control structure. Linearity survives where it is genuinely best (a rigid
   compliance render, say), as a plan the engine can still produce.

**What is gained by wrapping rather than rewriting.** OpenMontage's craft — its
tools, its tuned instructions, its checkpoints — is preserved and amplified. What
is added is *adaptivity* (arrangements no one pre-authored), *parallelism*
(independent branches by construction), *verifiability* (a validated graph instead
of a trusted sequence), and *continuity* (entities). The linear framework becomes
the substrate; the goal-driven layer becomes the composer on top of it.

---

## 5. When linear is still the right answer

This model is not a universal replacement, and adopting it uncritically would be a
mistake. Prefer a fixed pipeline when the process is genuinely invariant and its
correctness is legal or contractual rather than creative — a broadcast-compliance
render, a deterministic transcode, a regulated deliverable. Prefer it when there is
no meaningful choice to make, so a planner would only add latency and a failure
mode. And prefer it in the earliest bring-up of a new capability, before its
contract is understood well enough to type. The goal-driven engine earns its
complexity when the space of intents is wide, the capabilities are many and
reusable, correctness must be *proven* rather than assumed, and continuity across
steps matters. In those conditions — precisely the conditions of open-ended media
production — compiling the workflow from the goal is not just more flexible than
authoring it; it is more trustworthy.

---

## Sources

- [OpenMontage (GitHub)](https://github.com/calesthio/OpenMontage) — architecture: `tools/`, `skills/`, `pipeline_defs/`; the *research → proposal → script → scene plan → assets → edit → compose* pipeline.
- [OpenMontage/AGENT_GUIDE.md](https://github.com/calesthio/OpenMontage/blob/main/AGENT_GUIDE.md) — stage-director skills and human-approval checkpoints.
- [OpenMontage: The Open-Source AI Video Agent, Explained (VisionStory)](https://www.visionstory.ai/blog/product/how-to-use-openmontage)
- [OpenMontage Setup Guide (knightli.com)](https://knightli.com/en/2026/06/22/openmontage-ai-video-production-guide/)
- Reference implementation of the goal-driven model: `orchestrator/` in this repository; the normative contracts are in [`docs/goal-driven-workflow-spec.md`](./goal-driven-workflow-spec.md).
