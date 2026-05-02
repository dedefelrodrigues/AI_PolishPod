import asyncio
import hashlib
import os
import sys

import requests
from tqdm import tqdm


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

    tts_segments = [
        (i, seg) for i, seg in enumerate(segments) if seg["type"] != "pause"
    ]
    cached = sum(
        1 for _, seg in tts_segments
        if os.path.exists(_cache_path(
            subdir, seg["text"],
            config["voices"][_voice_role_for_segment(seg)] if not preview else _voice_role_for_segment(seg),
        ))
    )
    to_render = len(tts_segments) - cached
    print(f"  Segments: {len(tts_segments)} total, {cached} cached, {to_render} to render")

    paths: list[str | None] = [None] * len(segments)
    bar = tqdm(total=len(tts_segments), unit="seg", desc="Generating audio")
    for i, seg in tts_segments:
        text = seg["text"]
        voice_role = _voice_role_for_segment(seg)
        key_suffix = config["voices"][voice_role] if not preview else voice_role
        path = _cache_path(subdir, text, key_suffix)

        if not os.path.exists(path):
            bar.set_postfix_str(text[:40])
            render_segment(text, voice_role, path, config, preview)
        paths[i] = path
        bar.update(1)

    bar.close()
    return paths
