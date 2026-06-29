# RockBox orchestrator — CPU-only service that plans and runs media workflows.
# Build from the repo root:  docker build -f orchestrator/Dockerfile -t rockbox-orchestrator .
# It calls the GPU Pruna server (server.py) and/or Runway over HTTP — no torch here.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PORT=8001 \
    ARTIFACT_DIR=/data/artifacts

WORKDIR /app

COPY orchestrator/requirements.txt orchestrator/requirements.txt
RUN pip install --no-cache-dir -r orchestrator/requirements.txt

COPY orchestrator/ orchestrator/

VOLUME ["/data/artifacts"]
EXPOSE 8001

CMD ["sh", "-c", "uvicorn orchestrator.app:app --host 0.0.0.0 --port ${PORT}"]
