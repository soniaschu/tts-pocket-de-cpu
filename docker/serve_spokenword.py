import os

import uvicorn

import pocket_tts.main as app
from pocket_tts.models.tts_model import TTSModel


variant = "bucket_german"
default_voice = "/models/de/default.wav"
app.tts_model = TTSModel.load_model(variant)
app.global_model_state = app.tts_model.get_state_for_audio_prompt(default_voice, truncate=True)

uvicorn.run(
    app.web_app,
    host="0.0.0.0",
    port=int(os.environ.get("PORT", os.environ.get("SPOKENWORD_INTERNAL_PORT", "8000"))),
)