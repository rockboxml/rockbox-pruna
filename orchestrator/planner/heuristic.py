"""
Deterministic heuristic planner.

Backward-chains from the goal's target media type to a small workflow using the
registered skills. It covers the common image / video / narrated-video / audio
shapes, needs no network, and is the offline default and the LLM planner's
fallback. Entity threading is left to the binder, so plans here stay simple.
"""

from __future__ import annotations

from ..models import (
    Goal,
    InputBinding,
    MediaType,
    Plan,
    SkillSpec,
    WorkflowStep,
)
from ..skills.registry import SkillRegistry

_VIDEO_WORDS = ("video", "clip", "animate", "footage", "scene", "shot", "film")
_NARRATION_WORDS = ("narrat", "voiceover", "voice-over", "voice over", "speak", "say", "tells", "narrates")
_AUDIO_WORDS = ("voiceover", "narration", "speech", "audio", "sound", "music")


class HeuristicPlanner:
    def __init__(self, registry: SkillRegistry):
        self.registry = registry

    async def plan(self, goal: Goal, catalog: list[SkillSpec] | None = None) -> Plan:
        target = self._target(goal)
        if target == MediaType.VIDEO:
            return self._video_plan(goal)
        if target == MediaType.AUDIO:
            return self._audio_plan(goal)
        return self._image_plan(goal)

    # -- target detection --------------------------------------------------
    def _target(self, goal: Goal) -> MediaType:
        explicit = goal.constraints.get("target_media_type")
        if explicit:
            return MediaType(explicit)
        text = goal.text.lower()
        if any(w in text for w in _VIDEO_WORDS):
            return MediaType.VIDEO
        if any(w in text for w in _AUDIO_WORDS) and not any(
            w in text for w in _VIDEO_WORDS
        ):
            return MediaType.AUDIO
        return MediaType.IMAGE

    def _wants_narration(self, goal: Goal) -> bool:
        text = goal.text.lower()
        return any(w in text for w in _NARRATION_WORDS) or bool(
            goal.constraints.get("narration")
        )

    # -- recipes -----------------------------------------------------------
    def _image_plan(self, goal: Goal) -> Plan:
        self._require("generate_image")
        step = WorkflowStep(
            id="s1",
            skill_id="generate_image",
            params={"prompt": goal.text},
            rationale="Generate the requested image.",
        )
        return Plan(goal=goal, steps=[step], final_step="s1")

    def _audio_plan(self, goal: Goal) -> Plan:
        self._require("generate_audio")
        text = goal.constraints.get("narration") or goal.text
        step = WorkflowStep(
            id="s1",
            skill_id="generate_audio",
            params={"text": text},
            rationale="Generate the requested audio.",
        )
        return Plan(goal=goal, steps=[step], final_step="s1")

    def _video_plan(self, goal: Goal) -> Plan:
        self._require("generate_image", "generate_video")
        steps = [
            WorkflowStep(
                id="s1",
                skill_id="generate_image",
                params={"prompt": goal.text},
                rationale="Establish the first frame.",
            ),
            WorkflowStep(
                id="s2",
                skill_id="generate_video",
                params={"prompt": goal.text},
                input_bindings={"image": InputBinding(from_step="s1", port="image")},
                rationale="Animate the frame into a clip.",
            ),
        ]
        final = "s2"
        if self._wants_narration(goal) and self.registry.has("generate_audio") and self.registry.has("stitch"):
            narration = goal.constraints.get("narration") or goal.text
            steps.append(
                WorkflowStep(
                    id="s3",
                    skill_id="generate_audio",
                    params={"text": narration},
                    rationale="Generate the voiceover.",
                )
            )
            steps.append(
                WorkflowStep(
                    id="s4",
                    skill_id="stitch",
                    input_bindings={
                        "video": InputBinding(from_step="s2", port="video"),
                        "audio": InputBinding(from_step="s3", port="audio"),
                    },
                    rationale="Mux the clip and voiceover into the final video.",
                )
            )
            final = "s4"
        return Plan(goal=goal, steps=steps, final_step=final)

    def _require(self, *skill_ids: str) -> None:
        missing = [sid for sid in skill_ids if not self.registry.has(sid)]
        if missing:
            raise RuntimeError(
                f"heuristic planner needs skills {missing} but they are not registered"
            )
