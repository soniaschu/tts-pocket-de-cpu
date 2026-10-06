#!/bin/sh
set -eu

models_dir=/models
voices_dir=/voices
mkdir -p "$models_dir" "$voices_dir"

ln -sfn /models/de/lm_main.int8.onnx "$models_dir/flow_lm_main_int8.onnx"
ln -sfn /models/de/lm_flow.int8.onnx "$models_dir/flow_lm_flow_int8.onnx"
ln -sfn /models/de/decoder.int8.onnx "$models_dir/mimi_decoder_int8.onnx"
ln -sfn /models/de/encoder.onnx "$models_dir/mimi_encoder.onnx"
ln -sfn /models/de/text_conditioner.onnx "$models_dir/text_conditioner.onnx"
ln -sfn /models/de/bos_before_voice.npy "$models_dir/bos_before_voice.npy"
ln -sfn /models/de/default.wav "$voices_dir/de-default.wav"
ln -sfn /models/de/default.wav "$voices_dir/default.wav"

exec /usr/local/bin/pocket-tts \
    --server \
    --port "${RAVEN_PORT:-8080}" \
    --precision int8 \
    --threads "${RAVEN_THREADS:-4}" \
    --models-dir "$models_dir" \
    --voices-dir "$voices_dir" \
    --tokenizer /models/german/tokenizer.model