import os
import tempfile
import uuid
from pathlib import Path

import yaml
from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import FileResponse
from pydantic import BaseModel

from parse_lesson import ppl_to_json
from generate_audio import generate_audio
from build_lesson import build_lesson

app = FastAPI(title="AI_PolishPod API")

LESSONS_DIR = Path("lessons")
LESSONS_DIR.mkdir(exist_ok=True)

API_KEY = os.environ.get("POLISHPOD_API_KEY", "")


def _require_auth(x_api_key: str | None):
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")


def _load_config() -> dict:
    with open("config.yaml") as f:
        return yaml.safe_load(f)


class RenderRequest(BaseModel):
    script: str           # full .ppl content as a string
    provider: str = "google"  # preview | google | azure | elevenlabs
    output_name: str | None = None  # optional filename stem


class RenderResponse(BaseModel):
    filename: str
    duration_seconds: float
    download_url: str


@app.post("/render", response_model=RenderResponse)
def render(req: RenderRequest, x_api_key: str | None = Header(default=None)):
    _require_auth(x_api_key)

    if req.provider not in ("preview", "google", "azure", "elevenlabs"):
        raise HTTPException(status_code=400, detail=f"Unknown provider: {req.provider}")

    config = _load_config()

    with tempfile.TemporaryDirectory() as tmpdir:
        # Write .ppl to temp file
        ppl_path = os.path.join(tmpdir, "lesson.ppl")
        with open(ppl_path, "w") as f:
            f.write(req.script)

        # Parse to JSON
        _, script_data = ppl_to_json(ppl_path)

        # Generate audio segments
        audio_paths = generate_audio(script_data["segments"], config, provider=req.provider)

        # Build final MP3 (outside tmpdir so it persists)
        stem = req.output_name or f"lesson_{uuid.uuid4().hex[:8]}"
        output_stem = str(LESSONS_DIR / stem)
        output_path, duration_ms = build_lesson(script_data, script_data["segments"], audio_paths, output_stem)

    filename = Path(output_path).name
    return RenderResponse(
        filename=filename,
        duration_seconds=duration_ms / 1000,
        download_url=f"/download/{filename}",
    )


@app.get("/download/{filename}")
def download(filename: str, x_api_key: str | None = Header(default=None)):
    _require_auth(x_api_key)

    # Prevent path traversal
    safe_path = LESSONS_DIR / Path(filename).name
    if not safe_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(str(safe_path), media_type="audio/mpeg", filename=filename)


@app.get("/lessons")
def list_lessons(x_api_key: str | None = Header(default=None)):
    _require_auth(x_api_key)

    files = sorted(LESSONS_DIR.glob("*.mp3"))
    return [{"filename": f.name, "size_bytes": f.stat().st_size} for f in files]


@app.get("/health")
def health():
    return {"status": "ok"}
