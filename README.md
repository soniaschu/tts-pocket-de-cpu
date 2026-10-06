# Pocket TTS Docker Stack

This repo bundles the German Pocket TTS models into a sidecar-first Docker layout. The full bucket is synced into a host directory under `german/` with separate `models/` and `voices/` subfolders. Both services then read from the same synced local layout.

## Script control layer

The stack ships with a small script collection under `scripts/`:

```bash
./scripts/railpack.sh install
./scripts/railpack.sh build model-download
./scripts/railpack.sh build voice-download
./scripts/railpack.sh run start
./scripts/railpack.sh run stop
./scripts/railpack.sh run status
./scripts/railpack.sh run restart
```

This gives a simple command-line equivalent of start/stop/status and model/voice download actions.

## Remote API keys

The landing page on `http://localhost:8088` can create bearer tokens for the remote TTS services. Use the generated key in the `Authorization` header when calling the service from a remote client:

```bash
curl -H "Authorization: Bearer <your-key>" http://localhost:8000/health
curl -H "Authorization: Bearer <your-key>" http://localhost:8080/health
```

The generated keys are stored under the `german/` directory in `api_keys.json` and can be reused for remote OpenAI-compatible TTS clients.

## Railpack

Install the official Railway Railpack CLI from the upstream GitHub repository before using the deployment flow:

https://github.com/railwayapp/railpack

The bundled helper script installs the official release binary directly from the upstream repo and falls back to the upstream installer only if the release metadata is unavailable.

```bash
./scripts/railpack.sh install
railpack --help
```

## Landing page and admin controls

The stack exposes a small landing page on:

- http://localhost:8088

It shows:
- the current sidecar status
- number of model files
- number of voice files
- downloaded file count
- start, restart, and stop controls for the stack

This page acts as a lightweight admin panel for local deployment control.

## Docker Compose

Run both TTS services together from the workspace root:

```sh
docker compose up --build -d
```

Spokenword is exposed on `http://localhost:8000`; Raven is exposed on
`http://localhost:8080`. The first run downloads the complete public
`eysho-it/pocket-tts-models` bucket (about 2.3 GB) through the
`model-voice-assets` sidecar. The bucket is retained in a named Docker volume
and mirrored into the host-local `german/` directory for reuse across restarts.

Each app also has a separate named volume for its cache, outputs, and user
voice samples.

Manual controls:

```sh
docker compose up --build -d
docker compose restart
docker compose down
```

The Compose files use `1.1.1.1` for container DNS by default. Override it with
`DOCKER_DNS_SERVER` if your network requires a different resolver.

Spokenword loads the German BF16 checkpoint, tokenizer, and sample audio from
`german/models/` and `german/voices/`. Raven uses the matching German int8 ONNX
files under `german/models/de/` and the tokenizer from `german/models/german/`.
Its required `bos_before_voice.npy` is generated from the same German checkpoint
by the sidecar. The bucket remains available in the shared sidecar volume while
the runtime reads the synced host layout for the live stack.

Use `docker compose down` to stop services while retaining data. `docker compose
down -v` also removes the downloaded bucket, model caches, output audio, and
user voice samples.

## Railway deployment

Railway runs these as three independent services. Do not deploy the
`model-voice-assets` Compose sidecar: Railway volumes are private to each
service, so Spokenword and Raven bootstrap their own persistent model volume on
first start. The first deployment downloads the bucket separately for both
services and may take several minutes.

Create three services from this repository and use the repository root as each
service's build context. In each service's Settings, select the matching
Railway configuration file:

| Service | Config-as-code file | Volume mount | Health check |
| --- | --- | --- | --- |
| `landing` | `railway/landing.json` | `/german` | `/health` |
| `spokenword` | `railway/spokenword.json` | `/models` | `/health` |
| `raven` | `railway/raven.json` | `/models` | `/health` |

Set these service variables in Railway:

- `landing`: `POCKET_TTS_RAILWAY=1`, `STATE_DIR=/german`, `ADMIN_USERNAME`, and a strong secret `ADMIN_PASSWORD`. The service exits at startup if the password is missing or still `change-me`.
- `spokenword`: `POCKET_TTS_RAILWAY=1`, `HF_BUCKET_ID=eysho-it/pocket-tts-models`; add `HF_TOKEN` only if the bucket is private. Optionally set `OMP_NUM_THREADS`.
- `raven`: `POCKET_TTS_RAILWAY=1`, `HF_BUCKET_ID=eysho-it/pocket-tts-models`; add `HF_TOKEN` only if the bucket is private. Optionally set `RAVEN_THREADS`.

Railway injects `PORT`; do not set a fixed port. The services bind to that
port. Add a public domain only to services that need external access. Keep the
Landing admin service protected by its Basic Auth credentials. The dashboard's
Compose start/stop buttons are disabled in Railway; use Railway deployments to
restart services. The `/german` Landing volume preserves its dashboard state
and generated API keys. Each `/models` volume preserves the bucket cache and
prepared files for its own TTS service; the two model volumes are not shared.

For a local preflight, from this repository root run:

```sh
docker build -f docker/Dockerfile.landing -t pocket-tts-landing .
docker build -f docker/Dockerfile.spokenword -t pocket-tts-spokenword .
docker build -f docker/Dockerfile.raven -t pocket-tts-raven .
```

Railway deployments should use the matching config-as-code file above so each
service builds from the repository root with its own Dockerfile, health check,
and restart policy.

