"""
RockBox Pruna inference server.

A small FastAPI text-to-image server that loads a diffusers pipeline and
accelerates it with the open-source Pruna framework (`smash`). Published from the
public repo rockboxml/rockbox-pruna to ghcr.io/rockboxml/rockbox-pruna, and
launched on a GPU host by `@rockbox/deploy` (the Pruna workload).

Env:
  PRUNA_MODEL   HuggingFace model id (default: a tiny SD for fast cold start)
  PORT          listen port (default 8000)
  PRUNA_CACHER  pruna cacher algorithm (default: deepcache; "none" disables)
"""

import base64
import io
import os

from fastapi import FastAPI
from pydantic import BaseModel

MODEL_ID = os.environ.get("PRUNA_MODEL", "segmind/tiny-sd")
PORT = int(os.environ.get("PORT", "8000"))
CACHER = os.environ.get("PRUNA_CACHER", "deepcache")

app = FastAPI(title="rockbox-pruna")
_pipe = None


def _device():
    import torch

    return "cuda" if torch.cuda.is_available() else "cpu"


def get_pipe():
    """Lazily load + optimize the pipeline on first request."""
    global _pipe
    if _pipe is not None:
        return _pipe

    import torch
    from diffusers import AutoPipelineForText2Image

    device = _device()
    dtype = torch.float16 if device == "cuda" else torch.float32
    pipe = AutoPipelineForText2Image.from_pretrained(MODEL_ID, torch_dtype=dtype)
    pipe = pipe.to(device)

    # Accelerate with Pruna. Failures here are non-fatal — we still serve.
    if CACHER and CACHER.lower() != "none":
        try:
            from pruna import SmashConfig, smash

            cfg = SmashConfig()
            cfg["cacher"] = CACHER
            pipe = smash(model=pipe, smash_config=cfg)
            print(f"[pruna] smashed with cacher={CACHER}")
        except Exception as exc:  # noqa: BLE001
            print(f"[pruna] smash skipped: {exc}")

    _pipe = pipe
    return _pipe


class GenRequest(BaseModel):
    prompt: str
    num_inference_steps: int = 25
    guidance_scale: float = 7.5
    seed: int | None = None


@app.get("/health")
def health():
    return {"ok": True, "model": MODEL_ID, "device": _device()}


@app.post("/generate")
def generate(req: GenRequest):
    import torch

    pipe = get_pipe()
    generator = None
    if req.seed is not None:
        generator = torch.Generator(device=_device()).manual_seed(req.seed)

    image = pipe(
        req.prompt,
        num_inference_steps=req.num_inference_steps,
        guidance_scale=req.guidance_scale,
        generator=generator,
    ).images[0]

    buf = io.BytesIO()
    image.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    return {"image": f"data:image/png;base64,{b64}", "model": MODEL_ID}
