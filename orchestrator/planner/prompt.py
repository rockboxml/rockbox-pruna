"""
Prompt construction for the LLM planner.

The plan JSON contract *is* ``Plan.model_json_schema()`` (supplied to the model
via structured outputs), so the prompt only needs to convey the rules, the skill
catalog, and the cast. Keeping the schema as the single source of truth avoids
prose/code drift.
"""

from __future__ import annotations

import json

from ..entities import Entity
from ..models import Goal, SkillSpec

SYSTEM_PROMPT = """\
You are a media-production workflow planner. Given a GOAL, a CATALOG of skills, \
and a CAST of characters and locations, produce a directed acyclic graph (DAG) \
of steps that achieves the goal.

Each skill has typed input ports and output ports (image/video/audio/text) and a \
params JSON schema. Rules:
1. Use only skill ids that appear in the CATALOG.
2. Every required input port of a step must be satisfied by an upstream step's \
output port of the SAME media type (set input_bindings[port] = {from_step, port}) \
or a goal seed input (from_goal = index). Optional reference ports may be left \
unbound — the system fills them from the cast.
3. Fill each step's `params` to satisfy that skill's params schema.
4. For continuity, list the relevant cast members in each step's `entity_refs` \
(by their id) wherever a character or location appears — the system will thread \
their reference images/voice through so they stay on-model across the workflow.
5. Prefer the fewest steps and lowest total cost_hint that satisfies the goal.
6. Set `final_step` to the id of the step that produces the deliverable.

Return only the plan as JSON matching the provided schema."""


def build_user_prompt(goal: Goal, catalog: list[SkillSpec], cast: list[Entity]) -> str:
    catalog_json = json.dumps([spec.model_dump() for spec in catalog], indent=2)
    cast_json = json.dumps(
        [
            {
                "id": e.id,
                "name": e.name,
                "type": e.type.value,
                "descriptors": e.descriptors(),
                "has_baseline": bool(e.references),
            }
            for e in cast
        ],
        indent=2,
    )
    constraints = json.dumps(goal.constraints) if goal.constraints else "{}"
    seeds = json.dumps(
        [{"index": i, "media_type": s.media_type.value} for i, s in enumerate(goal.seed_inputs)]
    )
    return (
        f"GOAL:\n{goal.text}\n\n"
        f"GOAL CONSTRAINTS: {constraints}\n"
        f"GOAL SEED INPUTS: {seeds}\n\n"
        f"CAST:\n{cast_json}\n\n"
        f"CATALOG:\n{catalog_json}\n"
    )
