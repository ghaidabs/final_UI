from __future__ import annotations
import io
import logging
import os
from dataclasses import dataclass
from typing import Optional

from elevenlabs import VoiceSettings
from elevenlabs.client import ElevenLabs
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY")
DEFAULT_MODEL_ID = os.environ.get("ELEVENLABS_MODEL_ID")
DEFAULT_VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID")  

# PCM avoids mp3 decoding on playback
OUTPUT_FORMAT = "pcm_24000"
PCM_SAMPLE_RATE = 24_000

DEFAULT_VOICE_SETTINGS = VoiceSettings(
    stability=0.5,
    similarity_boost=0.75,
    style=0.0,
    use_speaker_boost=True,
    speed=1.0,
)


def _to_language_code(language: Optional[str]) -> Optional[str]:
    if not language:
        return None
    normalized = language.lower()
    if normalized.startswith("fr"):
        return "fr"
    if normalized.startswith("en"):
        return "en"
    return None


@dataclass
class SynthesisResult:
    audio_bytes: bytes
    sample_rate: int
    language_code: Optional[str] = None


class TTSSession:
    def __init__(
        self,
        api_key: Optional[str] = None,
        voice_id: Optional[str] = None,
        model_id: Optional[str] = None,
        voice_settings: Optional[VoiceSettings] = None,
    ):
        key = api_key or ELEVENLABS_API_KEY
        if not key:
            raise RuntimeError(
                "ELEVENLABS_API_KEY is not set. Add it to .env (see .env.example)."
            )

        self._client = ElevenLabs(api_key=key)
        self._voice_id = voice_id or DEFAULT_VOICE_ID
        self._model_id = model_id or DEFAULT_MODEL_ID
        self._voice_settings = voice_settings or DEFAULT_VOICE_SETTINGS

    def synthesize(self, text: str, language: Optional[str] = None) -> SynthesisResult:
        if not text or not text.strip():
            return SynthesisResult(audio_bytes=b"", sample_rate=PCM_SAMPLE_RATE)

        language_code = _to_language_code(language)

        kwargs = dict(
            voice_id=self._voice_id,
            model_id=self._model_id,
            output_format=OUTPUT_FORMAT,
            text=text,
            voice_settings=self._voice_settings,
        )
        if language_code:
            kwargs["language_code"] = language_code

        response = self._client.text_to_speech.stream(**kwargs)

        buffer = io.BytesIO()
        for chunk in response:
            if chunk:
                buffer.write(chunk)

        audio_bytes = buffer.getvalue()
        logger.info(
            "TTS: %d chars -> %d bytes pcm (voice=%s, model=%s, lang=%s)",
            len(text), len(audio_bytes), self._voice_id, self._model_id, language_code,
        )

        return SynthesisResult(
            audio_bytes=audio_bytes,
            sample_rate=PCM_SAMPLE_RATE,
            language_code=language_code,
        )