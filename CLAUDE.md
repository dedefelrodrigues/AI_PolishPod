# AI_PolishPod — Claude Code Project Guide

## What this project is

AI_PolishPod is a personal Polish language learning tool that generates Pimsleur-style audio lessons as MP3 files. Scripts are written in a human-readable `.ppl` format, parsed to JSON, rendered to per-segment audio via TTS, then stitched into a single MP3 using ffmpeg.

## Running a build

```bash
# Preview (free, local edge-tts voices — fast)
python3 main.py --script scripts/LESSON_005_v2.ppl

# Final with Google Chirp3-HD (~$0.16/lesson, best quality)
python3 main.py --script scripts/LESSON_005_v2.ppl --provider google

# Final with Azure Neural (free tier 500k chars/mo)
python3 main.py --script scripts/LESSON_005_v2.ppl --provider azure

# Final with ElevenLabs (credits exhausted as of 2026-05-02)
python3 main.py --script scripts/LESSON_005_v2.ppl --provider elevenlabs
```

Output lands in `lessons/`. Preview files are prefixed with `PREVIEW_`.

## Pipeline

```
.ppl  →  parse_lesson.py  →  .json  →  generate_audio.py  →  build_lesson.py  →  lessons/*.mp3
```

1. `parse_lesson.py` — converts `.ppl` to `.json` (runs automatically when `--script` points to a `.ppl`)
2. `generate_audio.py` — renders each non-pause segment to an MP3, caching by MD5 hash of text + voice ID
3. `build_lesson.py` — concatenates segments (inserting ffmpeg-generated silence for `PAUSE:`) into a final MP3

## Project structure

```
main.py                  # CLI entry point
parse_lesson.py          # .ppl → .json parser
generate_audio.py        # TTS rendering + cache logic
build_lesson.py          # ffmpeg concat + duration probe
config.yaml              # API keys + voice IDs for all providers
google_credentials.json  # Google service account key (gitignored)
requirements.txt         # Python dependencies
scripts/                 # lesson source files (.ppl)
  parsed/                # parsed output (.json) — auto-generated from .ppl
lessons/                 # rendered MP3 output
cache/
  preview/               # edge-tts renders
  google/                # Google Chirp3-HD renders
  azure/                 # Azure Neural renders
  elevenlabs/            # ElevenLabs renders
```

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

| Keyword     | JSON type       | Voice            | Notes                          |
| ----------- | --------------- | ---------------- | ------------------------------ |
| `NARRATOR:` | `narrator_en`   | English narrator |                                |
| `MAN:`      | `dialogue_pl`   | Polish male      | speaker = "man"                |
| `WOMAN:`    | `dialogue_pl`   | Polish female    | speaker = "woman"              |
| `RECALL:`   | `recall_prompt` | English narrator | Followed by a long pause       |
| `PAUSE:`    | `pause`         | —                | Silence only; value in seconds |
| `---`       | (ignored)       | —                | Section divider                |

## TTS modes

| Provider | Flag | Quality | Cost | Cache dir |
|---|---|---|---|---|
| edge-tts | (default) | Good | Free | `cache/preview/` |
| Google Chirp3-HD | `--provider google` | Best | ~$16/1M chars | `cache/google/` |
| Azure Neural | `--provider azure` | Good | 500k free/mo | `cache/azure/` |
| ElevenLabs | `--provider elevenlabs` | Excellent | Credits (exhausted) | `cache/elevenlabs/` |

The `--final` flag is a legacy alias for `--provider elevenlabs`.

Cache keys include the voice name/ID, so swapping a voice in `config.yaml` correctly invalidates cached audio.

### Google credentials
Place `google_credentials.json` (service account key) in the project root. It is gitignored.

### Estimating Google cost before rendering
```bash
python3 -c "
import re
chars = sum(len(l.split(':', 1)[1].strip()) for l in open('scripts/YOUR.ppl')
            if re.match(r'(NARRATOR|MAN|WOMAN|RECALL):', l.strip()))
print(f'{chars:,} chars  ~\${chars/1e6*16:.4f}')
"
```

## Dependencies

Python packages: `pip install -r requirements.txt`

System requirements: `ffmpeg` must be on `PATH` (used for silence generation and concat).

## Publishing

Finished MP3s are uploaded manually to RSS.com (free plan) for private podcast distribution. The feed URL is added to any podcast app for cross-device playback.

Future: `publish.py` may auto-generate `docs/podcast.xml` for GitHub Pages self-hosting.

## Lesson design principles

When writing, reviewing, or generating `.ppl` lesson scripts, follow these rules:

### Structure

1. Open with a full dialogue played through once (6–10 exchanges between MAN and WOMAN)
2. Break down each phrase: play in Polish → English translation → pause to repeat → play again
3. Recall rounds in the middle: NARRATOR prompts in English → long pause → answer revealed
4. Introduce new vocabulary mid-lesson using the same introduce/repeat/recall loop
5. Final review: all phrases recalled in shuffled order
6. Close with the full dialogue played again
7. NARRATOR outro summarising all phrases learned + preview of next lesson

### Vocabulary load

- **8–12 new phrases per lesson** — depth over breadth, never more
- Each new phrase must be **recycled at least 3 times** across the lesson
- Prefer high-frequency, practical phrases over exotic vocabulary

### Graduated interval recall (spacing within a lesson)

Each phrase should be recalled at increasing time gaps after first exposure:

- 1st recall: ~25 seconds after introduction
- 2nd recall: ~2 minutes after introduction
- 3rd recall: ~8 minutes after introduction
- 4th recall (if present): ~14 minutes after introduction

### Pause lengths

| Context                       | Duration                    |
| ----------------------------- | --------------------------- |
| After Polish dialogue segment | 4 seconds                   |
| After RECALL prompt           | 6 seconds                   |
| After NARRATOR explanation    | 0.5–1 second                |
| Between full dialogue lines   | 0 (no pause keyword needed) |

### Duration calibration

- Target: **~15 minutes** of final rendered audio
- Measured baseline: ~8.5 minutes per half a full-length script
- When estimating, assume ~3 words/second for speech + pause seconds

### Language level guidelines

| Level | Sentence complexity                  | Vocabulary                      |
| ----- | ------------------------------------ | ------------------------------- |
| A1    | Single clause, present tense only    | Greetings, numbers, basic nouns |
| A2    | Two clauses, basic past/future       | Daily activities, weather, food |
| B1    | Subordinate clauses, reflexive verbs | Opinions, plans, narrative      |
| B2    | Complex sentences, subjunctive hints | Abstract topics, nuance         |

### What NOT to do

- Do not introduce more than 2 new phrases in a row without a recall of an earlier one
- Do not use the word "Pimsleur" anywhere in scripts, titles, or descriptions — it is a registered trademark
- Do not write RECALL prompts in Polish — they are always in English
- Do not skip the opening full dialogue or the closing replay

## Config

`config.yaml` contains API keys and voice IDs for all providers. Do not commit this file to a public repository. `google_credentials.json` is also gitignored.

### Changing voices
Update the relevant section in `config.yaml` (`google:`, `azure:`, `preview:`). The cache key includes the voice name, so any change automatically invalidates cached audio for that provider.

Available Polish voices can be listed at runtime:
```bash
# Google
python3 -c "
import os; os.environ['GOOGLE_APPLICATION_CREDENTIALS']='google_credentials.json'
from google.cloud import texttospeech
c = texttospeech.TextToSpeechClient()
for v in c.list_voices(language_code='pl-PL').voices: print(v.name, v.ssml_gender)
"
```
