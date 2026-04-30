import argparse
import json
import os
import sys

import yaml

from build_lesson import build_lesson
from generate_audio import generate_audio
from parse_lesson import ppl_to_json

VALID_TYPES = {"narrator_en", "dialogue_pl", "recall_prompt", "pause"}
VALID_SPEAKERS = {"man", "woman"}


def load_config(path: str = "config.yaml") -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def load_script(path: str) -> dict:
    try:
        with open(path) as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: script file not found: {path}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: malformed JSON in {path}: {e}")
        sys.exit(1)

    for field in ("lesson_number", "topic", "segments"):
        if field not in data:
            print(f"Error: script missing required field '{field}'")
            sys.exit(1)

    if not isinstance(data["segments"], list):
        print("Error: 'segments' must be a list")
        sys.exit(1)

    for i, seg in enumerate(data["segments"]):
        if "type" not in seg:
            print(f"Error: segment {i} missing 'type'")
            sys.exit(1)
        if seg["type"] not in VALID_TYPES:
            print(f"Error: segment {i} has unknown type '{seg['type']}'")
            sys.exit(1)
        if seg["type"] == "dialogue_pl":
            if "speaker" not in seg:
                print(f"Error: segment {i} (dialogue_pl) missing 'speaker'")
                sys.exit(1)
            if seg["speaker"] not in VALID_SPEAKERS:
                print(f"Error: segment {i} speaker must be 'man' or 'woman', got '{seg['speaker']}'")
                sys.exit(1)
        if seg["type"] == "pause" and "seconds" not in seg:
            print(f"Error: segment {i} (pause) missing 'seconds'")
            sys.exit(1)
        if seg["type"] != "pause" and "text" not in seg:
            print(f"Error: segment {i} ({seg['type']}) missing 'text'")
            sys.exit(1)

    return data


def format_duration(ms: int) -> str:
    total_seconds = ms // 1000
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes}:{seconds:02d}"


def main():
    parser = argparse.ArgumentParser(description="Generate an AI_PolishPod audio lesson")
    parser.add_argument("--script", required=True, help="Path to lesson script (.ppl or .json)")
    parser.add_argument("--final", action="store_true", help="Use ElevenLabs TTS instead of local edge-tts")
    args = parser.parse_args()

    config = load_config()

    script_path = args.script
    if script_path.endswith(".ppl"):
        script_path, _ = ppl_to_json(script_path)
        print(f"Parsed: {script_path}")
        print()

    script = load_script(script_path)

    print(f"Lesson {script['lesson_number']}: {script['topic']}")
    print(f"Segments: {len(script['segments'])}")
    print()

    preview = not args.final
    audio_paths = generate_audio(script["segments"], config, preview=preview)

    print()
    output_stem = args.script
    if preview:
        base = os.path.splitext(os.path.basename(args.script))[0]
        output_stem = os.path.join(os.path.dirname(args.script), f"PREVIEW_{base}")
    output_path, duration_ms = build_lesson(script, script["segments"], audio_paths, output_stem)

    print()
    print(f"Output:   {output_path}")
    print(f"Duration: {format_duration(duration_ms)}")


if __name__ == "__main__":
    main()
