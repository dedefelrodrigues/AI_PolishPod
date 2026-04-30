# AI PolishPod

A personal Polish language learning tool that generates Pimsleur-style audio lessons as MP3 files. Lessons are written in a human-readable `.ppl` script format, parsed to JSON, rendered to audio via TTS, and stitched into a single MP3.

## How it works

```
.ppl  →  parse_lesson.py  →  .json  →  generate_audio.py  →  build_lesson.py  →  lessons/*.mp3
```

1. **`parse_lesson.py`** — converts `.ppl` scripts to `.json` (runs automatically when `--script` points to a `.ppl`)
2. **`generate_audio.py`** — renders each segment to MP3, caching by MD5 hash of text + voice
3. **`build_lesson.py`** — concatenates segments (inserting ffmpeg silence for `PAUSE:`) into the final MP3

## Setup

**Requirements:** Python 3.10+, `ffmpeg` on `PATH`

```bash
pip install -r requirements.txt
cp config.yaml.example config.yaml
# Edit config.yaml and add your ElevenLabs API key and voice IDs
```

## Running a build

```bash
# Preview — free, local edge-tts voices (fast)
python main.py --script scripts/LESSON_005_v2.ppl

# Final — ElevenLabs API (costs credits)
python main.py --script scripts/LESSON_005_v2.ppl --final
```

Output lands in `lessons/`. Preview files are prefixed with `PREVIEW_`.

## Script format (.ppl)

```
LESSON: 5
TOPIC: Spring is here
LEVEL: A2

---

NARRATOR: In this lesson you will learn...

PAUSE: 1

MAN: Dzień dobry, jaka piękna pogoda.
WOMAN: Tak, jest ciepło i słońce świeci.

RECALL: How do you say: it is warm?

PAUSE: 6

WOMAN: Jest ciepło.
```

| Keyword     | Voice            | Notes                          |
|-------------|------------------|--------------------------------|
| `NARRATOR:` | English narrator |                                |
| `MAN:`      | Polish male      |                                |
| `WOMAN:`    | Polish female    |                                |
| `RECALL:`   | English narrator | Followed by a long pause       |
| `PAUSE:`    | —                | Silence only; value in seconds |
| `---`       | —                | Section divider (ignored)      |

See `scripts/sample.ppl` for a full example.

## TTS modes

| Mode    | Engine      | Cost         | Cache location     |
|---------|-------------|--------------|-------------------|
| Preview | edge-tts    | Free         | `cache/preview/`  |
| Final   | ElevenLabs  | API credits  | `cache/elevenlabs/` |

Cache keys include the voice ID, so changing a voice in `config.yaml` correctly invalidates cached audio.

## Project structure

```
main.py              # CLI entry point
parse_lesson.py      # .ppl → .json parser
generate_audio.py    # TTS rendering + cache logic
build_lesson.py      # ffmpeg concat + duration probe
config.yaml.example  # config template (copy to config.yaml and fill in)
config.yaml          # your API keys — not committed
requirements.txt
scripts/             # lesson source files (.ppl)
  parsed/            # auto-generated .json output
  sample.ppl         # example script
lessons/             # rendered MP3 output (not committed)
cache/               # TTS audio cache (not committed)
```

## Publishing

Finished MP3s are uploaded to RSS.com (free plan) for private podcast distribution and played back in any podcast app.
