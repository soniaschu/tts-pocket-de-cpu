#!/bin/sh
set -eu

models_dir="${MODEL_OUT_DIR:-/models}"
voices_dir="${VOICE_OUT_DIR:-/voices}"
mkdir -p "$models_dir" "$voices_dir"

if [ "${POCKET_TTS_RAILWAY:-0}" = "1" ]; then
    python3 /app/sync_hf_bucket.py
fi

ln -sfn "$models_dir/de/lm_main.int8.onnx" "$models_dir/flow_lm_main_int8.onnx"
ln -sfn "$models_dir/de/lm_flow.int8.onnx" "$models_dir/flow_lm_flow_int8.onnx"
ln -sfn "$models_dir/de/decoder.int8.onnx" "$models_dir/mimi_decoder_int8.onnx"
ln -sfn "$models_dir/de/encoder.onnx" "$models_dir/mimi_encoder.onnx"
ln -sfn "$models_dir/de/text_conditioner.onnx" "$models_dir/text_conditioner.onnx"
ln -sfn "$models_dir/de/bos_before_voice.npy" "$models_dir/bos_before_voice.npy"
ln -sfn "$models_dir/de/default.wav" "$voices_dir/de-default.wav"
ln -sfn "$models_dir/de/default.wav" "$voices_dir/default.wav"

exec /usr/local/bin/pocket-tts \
    --server \
    --port "${PORT:-${RAVEN_PORT:-8080}}" \
    --precision int8 \
    --threads "${RAVEN_THREADS:-4}" \
    --models-dir "$models_dir" \
    --voices-dir "$voices_dir" \
    --tokenizer "$models_dir/german/tokenizer.model"