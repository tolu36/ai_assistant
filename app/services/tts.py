import base64
import os
import re
from typing import Dict

import httpx

from config import (
    MISTRAL_API_KEY,
    MISTRAL_TTS_API_URL,
    MISTRAL_TTS_MAX_CHARS,
    MISTRAL_TTS_MODEL,
    MISTRAL_TTS_RESPONSE_FORMAT,
    MISTRAL_TTS_VOICE_ID,
    OUTBOUND_HTTP_TRUST_ENV,
)


class TextToSpeechError(RuntimeError):
    pass


MEDIA_TYPES = {
    "mp3": "audio/mpeg",
    "wav": "audio/wav",
    "flac": "audio/flac",
    "opus": "audio/ogg",
    "pcm": "application/octet-stream",
}


def _env(name: str, default: str = "") -> str:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return value


def _mistral_api_key() -> str:
    return _env("MISTRAL_API_KEY", MISTRAL_API_KEY)


def _response_format() -> str:
    value = _env("MISTRAL_TTS_RESPONSE_FORMAT", MISTRAL_TTS_RESPONSE_FORMAT).lower()
    return value if value in MEDIA_TYPES else "mp3"


def _clean_tts_text(text: str) -> str:
    cleaned = re.sub(r"https?://\S+", " ", text or "")
    cleaned = re.sub(r"[*_`#>]+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def tts_status() -> Dict[str, object]:
    response_format = _response_format()
    return {
        "provider": "mistral",
        "enabled": bool(_mistral_api_key()),
        "model": _env("MISTRAL_TTS_MODEL", MISTRAL_TTS_MODEL),
        "voice_configured": bool(_env("MISTRAL_TTS_VOICE_ID", MISTRAL_TTS_VOICE_ID)),
        "response_format": response_format,
        "media_type": MEDIA_TYPES[response_format],
        "max_chars": int(_env("MISTRAL_TTS_MAX_CHARS", str(MISTRAL_TTS_MAX_CHARS))),
    }


def generate_mistral_speech(text: str) -> Dict[str, object]:
    api_key = _mistral_api_key()
    if not api_key:
        raise TextToSpeechError("MISTRAL_API_KEY is not configured.")

    max_chars = int(_env("MISTRAL_TTS_MAX_CHARS", str(MISTRAL_TTS_MAX_CHARS)))
    cleaned = _clean_tts_text(text)
    if not cleaned:
        raise TextToSpeechError("Text is required for speech generation.")
    if len(cleaned) > max_chars:
        raise TextToSpeechError(f"Text is too long for one speech request. Limit is {max_chars} characters.")

    response_format = _response_format()
    payload = {
        "model": _env("MISTRAL_TTS_MODEL", MISTRAL_TTS_MODEL),
        "input": cleaned,
        "response_format": response_format,
        "stream": False,
    }
    voice_id = _env("MISTRAL_TTS_VOICE_ID", MISTRAL_TTS_VOICE_ID)
    if voice_id:
        payload["voice_id"] = voice_id

    try:
        with httpx.Client(timeout=60, trust_env=OUTBOUND_HTTP_TRUST_ENV) as client:
            response = client.post(
                _env("MISTRAL_TTS_API_URL", MISTRAL_TTS_API_URL),
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text[:300] if exc.response is not None else str(exc)
        raise TextToSpeechError(f"Mistral TTS request failed: {detail}") from exc
    except httpx.HTTPError as exc:
        raise TextToSpeechError(f"Mistral TTS request failed: {exc}") from exc

    try:
        audio_data = response.json().get("audio_data", "")
        audio_bytes = base64.b64decode(audio_data)
    except Exception as exc:
        raise TextToSpeechError("Mistral TTS response did not contain valid audio data.") from exc

    if not audio_bytes:
        raise TextToSpeechError("Mistral TTS returned empty audio.")

    return {
        "audio": audio_bytes,
        "media_type": MEDIA_TYPES[response_format],
        "response_format": response_format,
    }
