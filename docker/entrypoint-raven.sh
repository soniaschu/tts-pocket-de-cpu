#!/bin/sh
set -eu

models_dir=/tmp/raven-models
voices_dir=/data/voices
mkdir -p "$models_dir" "$voices_dir"

ln -sfn /bucket/de/lm_main.int8.onnx "$models_dir/flow_lm_main_int8.onnx"
ln -sfn /bucket/de/lm_flow.int8.onnx "$models_dir/flow_lm_flow_int8.onnx"
ln -sfn /bucket/de/decoder.int8.onnx "$models_dir/mimi_decoder_int8.onnx"
ln -sfn /bucket/de/encoder.onnx "$models_dir/mimi_encoder.onnx"
ln -sfn /bucket/de/text_conditioner.onnx "$models_dir/text_conditioner.onnx"
ln -sfn /bucket/de/bos_before_voice.npy "$models_dir/bos_before_voice.npy"
ln -sfn /bucket/de/default.wav "$voices_dir/de-default.wav"

exec /usr/local/bin/pocket-tts \
    --server \
    --port "${RAVEN_PORT:-8080}" \
    --precision int8 \
    --threads "${RAVEN_THREADS:-4}" \
    --models-dir "$models_dir" \
    --voices-dir "$voices_dir" \
    --tokenizer /bucket/german/tokenizer.model