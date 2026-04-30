import asyncio
import hashlib
import os
import sys

import requests


def _voice_role_for_segment(segment: dict) -> str:
    seg_type = segment["type"]
    if seg_type in ("narrator_en", "recall_prompt"):
        return "narrator_en"
    if seg_type == "dialogue_pl":
        return f"polish_{segment['speaker']}"
    raise ValueError(f"Unexpected segment type for TTS: {seg_type}")


def _cache_path(subdir: str, text: str, key_suffix: str) -> str:
    key = hashlib.md5((text + key_suffix).encode()).hexdigest()
    return os.path.join("cache", subdir, f"{key}.mp3")


def render_segment_elevenlabs(text: str, voice_id: str, output_path: str, config: dict) -> None:
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {"xi-api-key": config["elevenlabs_api_key"]}
    body = {
        "text": text,
        "model_id": config["elevenlabs_model"],
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
    }
    resp = requests.post(url, headers=headers, json=body)
    if resp.status_code != 200:
        print(f"ElevenLabs error {resp.status_code}: {resp.text}")
        sys.exit(1)
    with open(output_path, "wb") as f:
        f.write(resp.content)


async def _render_edge_tts(text: str, voice: str, output_path: str) -> None:
    import edge_tts
    await edge_tts.Communicate(text, voice).save(output_path)


def render_segment_preview(text: str, voice_role: str, output_path: str, config: dict) -> None:
    preview_cfg = config.get("preview", {})
    voice = preview_cfg.get(voice_role, "en-US-AndrewNeural")
    asyncio.run(_render_edge_tts(text, voice, output_path))


def render_segment(
    text: str,
    voice_role: str,
    output_path: str,
    config: dict,
    preview: bool = False,
) -> None:
    if preview:
        render_segment_preview(text, voice_role, output_path, config)
    else:
        voice_id = config["voices"][voice_role]
        render_segment_elevenlabs(text, voice_id, output_path, config)


def generate_audio(
    segments: list[dict], config: dict, preview: bool = False
) -> list[str | None]:
    subdir = "preview" if preview else "elevenlabs"
    os.makedirs(os.path.join("cache", subdir), exist_ok=True)

    paths: list[str | None] = []
    for seg in segments:
        if seg["type"] == "pause":
            paths.append(None)
            continue

        text = seg["text"]
        voice_role = _voice_role_for_segment(seg)
        # ElevenLabs key includes voice_id so swapping a voice invalidates cache.
        # Preview key uses voice_role (edge-tts voice is fixed in config).
        key_suffix = config["voices"][voice_role] if not preview else voice_role
        path = _cache_path(subdir, text, key_suffix)

        if not os.path.exists(path):
            label = "Preview " if preview else "Rendering"
            print(f"  {label}: {seg['type']} — {text[:60]}")
            render_segment(text, voice_role, path, config, preview)
        else:
            print(f"  Cached:    {seg['type']} — {text[:60]}")

        paths.append(path)

    return paths
