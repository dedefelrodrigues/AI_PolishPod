import os
import re
import subprocess
import sys
import tempfile


def _slugify(text: str) -> str:
    text = text.lower().replace(" ", "_")
    text = re.sub(r"[^\w]", "", text)
    return text


def _make_silence(path: str, duration_s: float) -> None:
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo",
            "-t", str(duration_s),
            "-ar", "44100", "-ac", "2", "-b:a", "128k",
            path,
        ],
        check=True,
        capture_output=True,
    )


def build_lesson(
    meta: dict,
    segments: list[dict],
    audio_paths: list[str | None],
    script_path: str = "",
) -> tuple[str, int]:
    os.makedirs("lessons", exist_ok=True)

    if script_path:
        base = os.path.splitext(os.path.basename(script_path))[0]
    else:
        slug = _slugify(meta["topic"])
        base = f"{meta['lesson_number']:03d}_{slug}"
    output_path = os.path.join("lessons", f"{base}.mp3")

    with tempfile.TemporaryDirectory() as tmpdir:
        parts: list[str] = []

        for i, (seg, path) in enumerate(zip(segments, audio_paths)):
            if seg["type"] == "pause":
                silence = os.path.join(tmpdir, f"part_{i:03d}.mp3")
                _make_silence(silence, seg["seconds"])
                parts.append(silence)
            else:
                parts.append(path)

        list_path = os.path.join(tmpdir, "concat.txt")
        with open(list_path, "w") as f:
            for p in parts:
                f.write(f"file '{os.path.abspath(p)}'\n")

        result = subprocess.run(
            [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0", "-i", list_path,
                "-ar", "44100", "-ac", "2", "-b:a", "128k",
                output_path,
            ],
            capture_output=True,
        )
        if result.returncode != 0:
            print(result.stderr.decode())
            sys.exit(1)

        probe = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                output_path,
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        duration_ms = int(float(probe.stdout.strip()) * 1000)

    return output_path, duration_ms
