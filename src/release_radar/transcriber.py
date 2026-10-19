from __future__ import annotations

from pathlib import Path

import httpx

from .resilience import with_retries


def transcribe_audio(
    audio_path: Path,
    whisper_base_url: str,
    timeout: float,
    language: str = "pt",
) -> str:
    url = f"{whisper_base_url}/asr"
    params = {
        "task": "transcribe",
        "language": language,
        "output": "json",
        "word_timestamps": "False",
    }

    def send() -> dict:
        # Reabre o arquivo a cada tentativa: o corpo multipart consome o stream.
        with audio_path.open("rb") as audio_file:
            files = {"audio_file": (audio_path.name, audio_file, "audio/wav")}
            with httpx.Client(timeout=timeout) as client:
                response = client.post(url, params=params, files=files)
        response.raise_for_status()
        return response.json()

    data = with_retries(send, attempts=2, label="Whisper transcription")
    if "text" in data:
        return str(data.get("text") or "").strip()
    return " ".join(str(seg.get("text") or "").strip() for seg in data.get("segments", [])).strip()
