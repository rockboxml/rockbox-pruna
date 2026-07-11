# Vendored Runway skills

The Runway-backed skills (`generate_image`/`generate_video`/`generate_audio`)
shell out to the real [`runwayml/skills`](https://github.com/runwayml/skills)
scripts. Vendor them here as a git submodule:

```bash
git submodule add https://github.com/runwayml/skills orchestrator/vendor/runway-skills
git submodule update --init --recursive
```

The adapter (`orchestrator/skills/runway.py`) looks for
`orchestrator/vendor/runway-skills/skills/<skill>/scripts/*.py` (override the
location with `RUNWAY_SKILLS_DIR`). Runway skills are only registered when
`RUNWAYML_API_SECRET` is set; otherwise the orchestrator uses the built-in fakes
so everything still composes and runs offline.

The scripts run via `uv run scripts/*.py` and read `RUNWAYML_API_SECRET` from the
environment — the secret is never passed on the command line.
