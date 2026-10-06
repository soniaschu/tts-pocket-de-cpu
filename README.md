# -pocket-tts-models# tts-pocket-de-cpu.bkg
# tts-pocket-de-cpu.bkg

## Docker Compose

Run both TTS services together from the workspace root:

```sh
docker compose up --build
```

Spokenword is exposed on `http://localhost:8000`; Raven is exposed on
`http://localhost:8080`. The first run downloads the complete public
`eysho-it/pocket-tts-models` bucket (about 2.3 GB) through the
`model-voice-assets` sidecar. The bucket is kept in a named volume and reused
across restarts. Each app also has a separate named volume for its cache,
outputs, and user voice samples.

Each app can also be started independently from the workspace root:

```sh
docker compose -f pocket-tts-spokenword/compose.yaml up --build
docker compose -f pocket-tts-raven/compose.yaml up --build
```

The Compose files use `1.1.1.1` for container DNS by default. Override it with
`DOCKER_DNS_SERVER` if your network requires a different resolver.

Spokenword loads the German BF16 checkpoint, tokenizer, and sample audio from
`german/` and `de/`. Raven uses the matching German int8 ONNX files under `de/`
and the tokenizer from `german/`. Its required `bos_before_voice.npy` is
generated from the same German checkpoint by the sidecar. The downloaded
`german/embeddings/` remain available in the shared, read-only bucket volume;
Spokenword's API uses the bucket's default WAV as its initial voice and accepts
uploaded WAV prompts for voice cloning.

Use `docker compose down` to stop services while retaining data. `docker compose
down -v` also removes the downloaded bucket, model caches, output audio, and
user voice samples.
# tts-pocket-de-cpu.bkg
# tts-pocket-de-cpu
