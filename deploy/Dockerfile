# Deploy image for the RockBox orchestrator + Studio UI (NOT the GPU Pruna image).
# Multi-stage: Node builds the Studio SPA, then a slim Python image serves the
# FastAPI orchestrator with the built SPA mounted at /.
#
# Build from the repo root:
#   docker build -f deploy/Dockerfile -t rockbox-app .
# Railway uses this via railway.json (build.dockerfilePath).

# --- stage 1: build the Studio SPA ---
FROM node:22-slim AS studio
WORKDIR /studio
COPY studio/package.json studio/package-lock.json ./
RUN npm ci
COPY studio/ ./
RUN npm run build

# --- stage 2: the CPU Python service ---
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 \
    PLANNER_MODE=auto \
    ARTIFACT_DIR=/data/artifacts

WORKDIR /app

COPY orchestrator/requirements.txt orchestrator/requirements.txt
RUN pip install --no-cache-dir -r orchestrator/requirements.txt

COPY orchestrator/ orchestrator/
COPY --from=studio /studio/dist studio/dist

# Artifacts are written here; mount a Railway volume at /data to persist them.
VOLUME ["/data/artifacts"]

# Railway injects $PORT; fall back to 8001 for local runs.
EXPOSE 8001
CMD ["sh", "-c", "uvicorn orchestrator.app:app --host 0.0.0.0 --port ${PORT:-8001}"]
