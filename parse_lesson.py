import argparse
import json
import os
import sys

KNOWN_TAGS = {"LESSON", "TOPIC", "LEVEL", "NARRATOR", "MAN", "WOMAN", "RECALL", "PAUSE"}


def parse_ppl(path: str) -> dict:
    meta = {}
    segments = []

    try:
        with open(path, encoding="utf-8") as f:
            lines = f.readlines()
    except FileNotFoundError:
        print(f"Error: file not found: {path}")
        sys.exit(1)

    for lineno, raw in enumerate(lines, 1):
        line = raw.strip()
        if not line or line.startswith("---"):
            continue

        potential_tag = line.split(":")[0].strip().upper()
        is_new_tag = potential_tag in KNOWN_TAGS

        if not is_new_tag:
            # Continuation of the previous segment's text
            if segments and "text" in segments[-1]:
                segments[-1]["text"] += " " + line
                continue
            print(f"Error: line {lineno} has no ':' separator: {raw.rstrip()}")
            sys.exit(1)

        tag, _, value = line.partition(":")
        tag = tag.strip().upper()
        value = value.strip()

        if tag == "LESSON":
            try:
                meta["lesson_number"] = int(value)
            except ValueError:
                print(f"Error: line {lineno}: LESSON must be an integer, got '{value}'")
                sys.exit(1)
        elif tag == "TOPIC":
            meta["topic"] = value
        elif tag == "LEVEL":
            meta["level"] = value
        elif tag == "NARRATOR":
            segments.append({"type": "narrator_en", "text": value})
        elif tag == "MAN":
            segments.append({"type": "dialogue_pl", "speaker": "man", "text": value})
        elif tag == "WOMAN":
            segments.append({"type": "dialogue_pl", "speaker": "woman", "text": value})
        elif tag == "RECALL":
            segments.append({"type": "recall_prompt", "text": value})
        elif tag == "PAUSE":
            try:
                seconds = float(value)
            except ValueError:
                print(f"Error: line {lineno}: PAUSE must be a number, got '{value}'")
                sys.exit(1)
            segments.append({"type": "pause", "seconds": seconds})

    for field in ("lesson_number", "topic"):
        if field not in meta:
            print(f"Error: missing required header '{field.upper()}:'")
            sys.exit(1)

    return {**meta, "segments": segments}


def estimate_duration(segments: list[dict]) -> int:
    total_seconds = 0
    for seg in segments:
        if seg["type"] == "pause":
            total_seconds += seg["seconds"]
        else:
            word_count = len(seg["text"].split())
            total_seconds += word_count / 3
    return int(total_seconds)


def format_duration(seconds: int) -> str:
    return f"{seconds // 60}:{seconds % 60:02d}"


def ppl_to_json(ppl_path: str) -> str:
    script = parse_ppl(ppl_path)
    parsed_dir = os.path.join(os.path.dirname(ppl_path), "parsed")
    os.makedirs(parsed_dir, exist_ok=True)
    stem = os.path.splitext(os.path.basename(ppl_path))[0]
    json_path = os.path.join(parsed_dir, stem + ".json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(script, f, ensure_ascii=False, indent=2)
    return json_path, script


def main():
    parser = argparse.ArgumentParser(description="Parse a .ppl lesson script into JSON")
    parser.add_argument("script", help="Path to .ppl file")
    args = parser.parse_args()

    if not args.script.endswith(".ppl"):
        print("Error: input file must have a .ppl extension")
        sys.exit(1)

    json_path, script = ppl_to_json(args.script)
    segments = script["segments"]
    est_seconds = estimate_duration(segments)

    print(f"Lesson {script['lesson_number']}: {script['topic']}")
    print(f"Segments:           {len(segments)}")
    print(f"Estimated duration: {format_duration(est_seconds)}")
    print(f"Output:             {json_path}")


if __name__ == "__main__":
    main()
