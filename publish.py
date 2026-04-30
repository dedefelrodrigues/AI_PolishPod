import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from email.utils import formatdate

import yaml
from mutagen.mp3 import MP3

DOCS_DIR = "docs"
EPISODES_DIR = os.path.join(DOCS_DIR, "episodes")
PUBLISHED_JSON = os.path.join(DOCS_DIR, "published.json")
PODCAST_XML = os.path.join(DOCS_DIR, "podcast.xml")
LESSONS_DIR = "lessons"
PLACEHOLDER_URL = "https://yourusername.github.io/AI_PolishPod"

_LEVEL_RE = re.compile(r"^[AB][12]$")


def load_config() -> dict:
    with open("config.yaml") as f:
        return yaml.safe_load(f)


def parse_filename(filename: str) -> tuple[int, str, str] | None:
    stem = os.path.splitext(filename)[0]

    # Primary convention: LESSON{n}_{Word}_..._{Level?}
    m = re.match(r"^LESSON(\d+)_(.+)$", stem, re.IGNORECASE)
    if not m:
        # Fallback: {nnn}_{word}_...
        m = re.match(r"^(\d+)_(.+)$", stem)
    if not m:
        return None

    num = int(m.group(1))
    parts = m.group(2).split("_")
    if parts and _LEVEL_RE.match(parts[-1]):
        level = parts[-1]
        topic = " ".join(parts[:-1])
    else:
        level = ""
        topic = " ".join(parts)

    return num, topic, level


def mp3_duration_str(path: str) -> str:
    audio = MP3(path)
    total = int(audio.info.length)
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def pub_date(path: str) -> str:
    return formatdate(os.path.getmtime(path), usegmt=True)


def xml_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
    )


def build_xml(episodes: list[dict], podcast: dict) -> str:
    base_url = podcast["github_pages_url"].rstrip("/")

    items = []
    for ep in sorted(episodes, key=lambda e: e["lesson_number"]):
        title = f"Lesson {ep['lesson_number']} – {ep['topic']}"
        if ep["level"]:
            title += f" ({ep['level']})"
        desc = (
            f"Lesson {ep['lesson_number']} — {ep['topic']}."
            + (f" Level {ep['level']}." if ep["level"] else "")
            + " AI_PolishPod spaced repetition Polish lesson."
        )
        enclosure_url = f"{base_url}/episodes/{ep['filename']}"
        items.append(f"""\
    <item>
      <title>{xml_escape(title)}</title>
      <guid isPermaLink="false">{xml_escape(enclosure_url)}</guid>
      <description>{xml_escape(desc)}</description>
      <enclosure url="{xml_escape(enclosure_url)}"
                 length="{ep['size']}"
                 type="audio/mpeg"/>
      <itunes:duration>{ep['duration']}</itunes:duration>
      <pubDate>{ep['pub_date']}</pubDate>
    </item>""")

    cover = ""
    if podcast.get("cover_image_url"):
        cover = f"\n    <itunes:image href=\"{xml_escape(podcast['cover_image_url'])}\"/>"

    return f"""\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
     xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
  <channel>
    <title>{xml_escape(podcast['title'])}</title>
    <description>{xml_escape(podcast['description'])}</description>
    <language>{xml_escape(podcast['language'])}</language>
    <itunes:author>{xml_escape(podcast['author'])}</itunes:author>
    <link>{xml_escape(base_url)}</link>{cover}
{chr(10).join(items)}
  </channel>
</rss>
"""


def git(*args: str) -> None:
    result = subprocess.run(["git"] + list(args), capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Git error ({' '.join(args)}):\n{result.stderr.strip()}")
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish AI_PolishPod lessons to GitHub Pages")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be published without doing it")
    args = parser.parse_args()

    config = load_config()
    podcast = config.get("podcast", {})

    if not podcast:
        print("Error: 'podcast' section missing from config.yaml. See config.yaml.example.")
        sys.exit(1)

    base_url = podcast.get("github_pages_url", "")
    if not base_url or base_url == PLACEHOLDER_URL:
        print("Error: set 'podcast.github_pages_url' in config.yaml before publishing.")
        sys.exit(1)

    os.makedirs(EPISODES_DIR, exist_ok=True)

    published = []
    if os.path.exists(PUBLISHED_JSON):
        with open(PUBLISHED_JSON) as f:
            published = json.load(f)
    published_set = set(published)

    # Find all final (non-PREVIEW) MP3s in lessons/
    if not os.path.isdir(LESSONS_DIR):
        print("Nothing new to publish (lessons/ folder not found).")
        sys.exit(0)

    candidates = [
        f for f in os.listdir(LESSONS_DIR)
        if f.endswith(".mp3") and not f.startswith("PREVIEW_")
    ]

    new_files = [f for f in candidates if f not in published_set]

    if not new_files:
        print("Nothing new to publish.")
        sys.exit(0)

    # Parse and validate
    episodes_to_add = []
    for filename in new_files:
        parsed = parse_filename(filename)
        if parsed is None:
            print(f"Warning: cannot parse filename '{filename}', skipping.")
            continue
        lesson_number, topic, level = parsed
        src = os.path.join(LESSONS_DIR, filename)
        try:
            duration = mp3_duration_str(src)
        except Exception as e:
            print(f"Warning: could not read '{filename}' ({e}), skipping.")
            continue
        episodes_to_add.append({
            "filename": filename,
            "lesson_number": lesson_number,
            "topic": topic,
            "level": level,
            "duration": duration,
            "size": os.path.getsize(src),
            "pub_date": pub_date(src),
            "src": src,
        })

    if not episodes_to_add:
        print("Nothing new to publish.")
        sys.exit(0)

    if args.dry_run:
        print("Dry run — would publish:")
        for ep in sorted(episodes_to_add, key=lambda e: e["lesson_number"]):
            title = f"Lesson {ep['lesson_number']} – {ep['topic']}"
            if ep["level"]:
                title += f" ({ep['level']})"
            print(f"  {title}  [{ep['duration']}]  {ep['filename']}")
        sys.exit(0)

    # Copy MP3s
    for ep in episodes_to_add:
        dst = os.path.join(EPISODES_DIR, ep["filename"])
        shutil.copy2(ep["src"], dst)
        print(f"Copied: {ep['filename']}")

    # Rebuild full episode list for XML (all published + new)
    all_episodes = []

    # Reload already-published entries from their copies in docs/episodes/
    for filename in published_set:
        parsed = parse_filename(filename)
        if parsed is None:
            continue
        lesson_number, topic, level = parsed
        dst = os.path.join(EPISODES_DIR, filename)
        if not os.path.exists(dst):
            continue
        try:
            duration = mp3_duration_str(dst)
        except Exception:
            continue
        all_episodes.append({
            "filename": filename,
            "lesson_number": lesson_number,
            "topic": topic,
            "level": level,
            "duration": duration,
            "size": os.path.getsize(dst),
            "pub_date": pub_date(dst),
        })

    for ep in episodes_to_add:
        all_episodes.append({k: v for k, v in ep.items() if k != "src"})

    # Write podcast.xml
    xml = build_xml(all_episodes, podcast)
    with open(PODCAST_XML, "w", encoding="utf-8") as f:
        f.write(xml)
    print(f"Generated: {PODCAST_XML}")

    # Update published.json
    updated_published = sorted(published_set | {ep["filename"] for ep in episodes_to_add})
    with open(PUBLISHED_JSON, "w", encoding="utf-8") as f:
        json.dump(updated_published, f, indent=2)

    # Commit and push
    git("add", DOCS_DIR)

    new_nums = sorted(ep["lesson_number"] for ep in episodes_to_add)
    new_topics = [ep["topic"] for ep in sorted(episodes_to_add, key=lambda e: e["lesson_number"])]
    if len(episodes_to_add) == 1:
        msg = f"Publish lesson {new_nums[0]}: {new_topics[0]}"
    else:
        nums_str = ", ".join(str(n) for n in new_nums)
        msg = f"Publish lessons {nums_str}: batch update"

    git("commit", "-m", msg)
    print(f"Committed: {msg}")

    git("push", "origin", "main")
    print(f"Pushed to GitHub.")

    feed_url = base_url.rstrip("/") + "/podcast.xml"
    print(f"\nFeed URL: {feed_url}")


if __name__ == "__main__":
    main()
