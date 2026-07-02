from __future__ import annotations

import yt_dlp

VID = "https://www.youtube.com/watch?v=hEXZslPBIG8"

for clients in (["mweb"], ["web_safari"], ["mweb", "web_safari", "tv"]):
    # metadata
    opts = {"quiet": True, "no_warnings": True, "skip_download": True,
            "extractor_args": {"youtube": {"player_client": clients}}}
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(VID, download=False)
        fmts = info.get("formats") or []
        audio = [f for f in fmts if f.get("acodec") not in (None, "none") and f.get("vcodec") in (None, "none")]
        print(f"META OK {clients} desc_len={len(info.get('description') or '')} audio_formats={len(audio)}")
    except Exception as e:
        print(f"META FAIL {clients}: {str(e)[:70]}")
