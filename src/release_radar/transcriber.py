from __future__ import annotations

from pathlib import Path

import httpx


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
    with audio_path.open("rb") as audio_file:
        files = {"audio_file": (audio_path.name, audio_file, "audio/wav")}
        with httpx.Client(timeout=timeout) as client:
            response = client.post(url, params=params, files=files)
    response.raise_for_status()
    data = response.json()
    if "text" in data:
        return str(data.get("text") or "").strip()
    return " ".join(str(seg.get("text") or "").strip() for seg in data.get("segments", [])).strip()
