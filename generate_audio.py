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


def render_segment_google(text: str, voice_name: str, output_path: str, config: dict) -> None:
    from google.cloud import texttospeech
    import google.auth

    creds_file = config["google"].get("credentials_file")
    if creds_file:
        import os as _os
        _os.environ.setdefault("GOOGLE_APPLICATION_CREDENTIALS", creds_file)

    client = texttospeech.TextToSpeechClient()
    language_code = "-".join(voice_name.split("-")[:2])  # e.g. "pl-PL" from "pl-PL-Neural2-D"
    synthesis_input = texttospeech.SynthesisInput(text=text)
    voice = texttospeech.VoiceSelectionParams(
        language_code=language_code,
        name=voice_name,
    )
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3
    )
    response = client.synthesize_speech(
        input=synthesis_input, voice=voice, audio_config=audio_config
    )
    with open(output_path, "wb") as f:
        f.write(response.audio_content)


def render_segment_azure(text: str, voice_name: str, output_path: str, config: dict) -> None:
    import azure.cognitiveservices.speech as speechsdk

    speech_config = speechsdk.SpeechConfig(
        subscription=config["azure_speech_key"],
        region=config["azure_speech_region"],
    )
    speech_config.speech_synthesis_voice_name = voice_name
    speech_config.set_speech_synthesis_output_format(
        speechsdk.SpeechSynthesisOutputFormat.Audio16Khz128KBitRateMonoMp3
    )
    synthesizer = speechsdk.SpeechSynthesizer(
        speech_config=speech_config, audio_config=None
    )
    result = synthesizer.speak_text_async(text).get()
    if result.reason != speechsdk.ResultReason.SynthesizingAudioCompleted:
        print(f"Azure TTS error: {result.reason} — {result.cancellation_details.error_details if result.reason == speechsdk.ResultReason.Canceled else ''}")
        sys.exit(1)
    with open(output_path, "wb") as f:
        f.write(result.audio_data)


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
    provider: str = "preview",
) -> None:
    if provider == "preview":
        render_segment_preview(text, voice_role, output_path, config)
    elif provider == "azure":
        voice_name = config["azure"][voice_role]
        render_segment_azure(text, voice_name, output_path, config)
    elif provider == "google":
        voice_name = config["google"][voice_role]
        render_segment_google(text, voice_name, output_path, config)
    else:  # elevenlabs
        voice_id = config["voices"][voice_role]
        render_segment_elevenlabs(text, voice_id, output_path, config)


def _key_suffix_for(voice_role: str, config: dict, provider: str) -> str:
    if provider == "preview":
        return voice_role
    if provider == "azure":
        return config["azure"][voice_role]
    if provider == "google":
        return config["google"][voice_role]
    return config["voices"][voice_role]


def generate_audio(
    segments: list[dict], config: dict, provider: str = "preview"
) -> list[str | None]:
    subdir = provider
    os.makedirs(os.path.join("cache", subdir), exist_ok=True)

    tts_segments = [
        (i, seg) for i, seg in enumerate(segments) if seg["type"] != "pause"
    ]
    cached = sum(
        1 for _, seg in tts_segments
        if os.path.exists(_cache_path(
            subdir, seg["text"],
            _key_suffix_for(_voice_role_for_segment(seg), config, provider),
        ))
    )
    to_render = len(tts_segments) - cached
    paths: list[str | None] = [None] * len(segments)
    bar = tqdm(total=len(tts_segments), unit="seg", desc="Generating audio",
               bar_format="{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]")
    tqdm.write(f"  Segments: {len(tts_segments)} total, {cached} cached, {to_render} to render")
    for i, seg in tts_segments:
        text = seg["text"]
        voice_role = _voice_role_for_segment(seg)
        key_suffix = _key_suffix_for(voice_role, config, provider)
        path = _cache_path(subdir, text, key_suffix)

        if not os.path.exists(path):
            render_segment(text, voice_role, path, config, provider)
        paths[i] = path
        bar.update(1)

    bar.close()
    return paths
