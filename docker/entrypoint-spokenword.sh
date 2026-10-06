#!/bin/sh
set -eu

models_dir="${MODEL_OUT_DIR:-/models}"
mkdir -p "$models_dir"

if [ "${POCKET_TTS_RAILWAY:-0}" = "1" ] && [ ! -f "$models_dir/german/model.safetensors" ]; then
    python3 /app/sync_hf_bucket.py
fi

exec python /app/serve_spokenword.py
