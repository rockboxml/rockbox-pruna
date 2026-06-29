"""LLM planner tests with a stubbed Anthropic client — no real API calls."""

from __future__ import annotations

from orchestrator.models import Goal, InputBinding, WorkflowStep
from orchestrator.planner.llm import LLMPlanner, PlanDraft


class _Resp:
    def __init__(self, parsed):
        self.parsed_output = parsed


class _Messages:
    def __init__(self, outer):
        self._outer = outer

    async def parse(self, **kwargs):
        return self._outer._next()


class StubClient:
    """Returns queued PlanDrafts (or raises queued exceptions) from messages.parse."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0
        self.messages = _Messages(self)

    def _next(self):
        item = self._responses[self.calls]
        self.calls += 1
        if isinstance(item, Exception):
            raise item
        return item


def _valid_image_draft():
    return _Resp(
        PlanDraft(
            steps=[WorkflowStep(id="s1", skill_id="generate_image", params={"prompt": "x"})],
            final_step="s1",
        )
    )


def _invalid_draft():
    return _Resp(
        PlanDraft(
            steps=[WorkflowStep(id="s1", skill_id="does_not_exist")],
            final_step="s1",
        )
    )


async def test_valid_first_try(registry):
    client = StubClient([_valid_image_draft()])
    planner = LLMPlanner(registry, client=client)
    plan = await planner.plan(Goal(text="a cat"), registry.catalog())
    assert [s.skill_id for s in plan.steps] == ["generate_image"]
    assert client.calls == 1


async def test_repairs_after_invalid(registry):
    client = StubClient([_invalid_draft(), _valid_image_draft()])
    planner = LLMPlanner(registry, client=client)
    plan = await planner.plan(Goal(text="a cat"), registry.catalog())
    assert [s.skill_id for s in plan.steps] == ["generate_image"]
    assert client.calls == 2  # one repair round


async def test_falls_back_to_heuristic_when_always_invalid(registry):
    client = StubClient([_invalid_draft(), _invalid_draft(), _invalid_draft()])
    planner = LLMPlanner(registry, max_repair_rounds=2, client=client)
    # video goal so the heuristic fallback is distinguishable (multi-step)
    plan = await planner.plan(Goal(text="a video clip of a city"), registry.catalog())
    assert [s.skill_id for s in plan.steps] == ["generate_image", "generate_video"]
    assert client.calls == 3


async def test_falls_back_on_api_error(registry):
    client = StubClient([RuntimeError("api down")])
    planner = LLMPlanner(registry, client=client)
    plan = await planner.plan(Goal(text="a cat"), registry.catalog())
    assert [s.skill_id for s in plan.steps] == ["generate_image"]
