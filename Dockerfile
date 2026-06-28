# RockBox Pruna inference image — canonical build context for the public repo
# rockboxml/rockbox-pruna, published to ghcr.io/rockboxml/rockbox-pruna.
# Runs a diffusers pipeline accelerated with the open-source Pruna framework.
# Requires --gpus all at runtime.
FROM nvidia/cuda:12.1.1-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    PRUNA_MODEL=segmind/tiny-sd \
    PRUNA_CACHER=deepcache

RUN apt-get update && apt-get install -y --no-install-recommends \
      python3 python3-pip git ca-certificates && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install the CUDA build of torch first so pruna/diffusers resolve against it.
RUN pip3 install --no-cache-dir --upgrade pip && \
    pip3 install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cu121

COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY server.py .

# Model weights download from HuggingFace on first request into this cache.
VOLUME ["/root/.cache/huggingface"]
EXPOSE 8000

CMD ["sh", "-c", "uvicorn server:app --host 0.0.0.0 --port ${PORT}"]
