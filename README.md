# rockbox-pruna image

Canonical build context for the public image **`ghcr.io/rockboxml/rockbox-pruna`**.

A self-hosted Pruna inference server: a diffusers text-to-image pipeline
accelerated with the open-source [Pruna](https://github.com/PrunaAI/pruna)
framework (`smash`), behind a tiny FastAPI service. `@rockbox/deploy`'s Pruna
workload launches it on a GPU host (Latitude / RunPod / Vultr).

## Why a separate public repo

GHCR package visibility follows the building repo. Publishing from a **public**
repo in the **rockboxml** org makes the image public, so GPU hosts can `docker
pull` it with no registry credentials. This folder is the drop-in for that repo.

## Bootstrapping `rockboxml/rockbox-pruna`

```bash
# Create an empty PUBLIC repo "rockbox-pruna" in the rockboxml org, then:
cp -r infra/rockbox-pruna-image/* infra/rockbox-pruna-image/.github <target>/
cd <target> && git init && git add -A && git commit -m "init rockbox-pruna image"
git remote add origin git@github.com:rockboxml/rockbox-pruna.git
git push -u origin main
```

`.github/workflows/publish.yml` then builds on PRs (validate) and pushes
`:latest` + `:sha` on `main` / tags / manual dispatch using the repo's built-in
`GITHUB_TOKEN` — no secrets needed. First publish: make sure the package's
visibility is set to **Public** (Org → Packages → rockbox-pruna → Settings).

## Endpoints
- `GET /health` → `{ ok, model, device }`
- `POST /generate` → `{ image: "data:image/png;base64,…" }`
  body: `{ prompt, num_inference_steps?, guidance_scale?, seed? }`

## Env
| Var | Default | Meaning |
| --- | --- | --- |
| `PRUNA_MODEL` | `segmind/tiny-sd` | HuggingFace model id to serve |
| `PRUNA_CACHER` | `deepcache` | Pruna cacher (`none` disables optimization) |
| `PORT` | `8000` | listen port |

## Run locally (needs an NVIDIA GPU + container toolkit)
```bash
docker run --gpus all -p 8000:8000 \
  -e PRUNA_MODEL=stabilityai/sdxl-turbo \
  ghcr.io/rockboxml/rockbox-pruna:latest
curl -X POST localhost:8000/generate -H 'content-type: application/json' \
  -d '{"prompt":"a neon city at dusk","num_inference_steps":4}'
```
