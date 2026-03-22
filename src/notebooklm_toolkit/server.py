#!/usr/bin/env python3
"""
NotebookLM Toolkit — FastAPI Server

Serves the web UI and provides API endpoints for all toolkit features.
"""

import os
import json
import asyncio
import tempfile
import traceback
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from starlette.responses import StreamingResponse

app = FastAPI(title="NotebookLM Toolkit", version="2.0.0")

# Static files
STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Temp/upload directory
UPLOAD_DIR = Path(tempfile.gettempdir()) / "nlm_toolkit_uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR = Path(tempfile.gettempdir()) / "nlm_toolkit_output"
OUTPUT_DIR.mkdir(exist_ok=True)

# In-memory state for active jobs
_jobs = {}


# ------------------------------------------------------------------ #
#  Index                                                               #
# ------------------------------------------------------------------ #

@app.get("/", response_class=HTMLResponse)
async def index():
    return (STATIC_DIR / "index.html").read_text(encoding="utf-8")


# ------------------------------------------------------------------ #
#  Preflight                                                           #
# ------------------------------------------------------------------ #

@app.get("/api/preflight")
async def preflight():
    from .core.preflight import check_all
    return check_all()


# ------------------------------------------------------------------ #
#  PDF Cleaner API                                                     #
# ------------------------------------------------------------------ #

@app.post("/api/pdf/upload")
async def pdf_upload(files: list[UploadFile] = File(...)):
    """Upload PDF files for processing."""
    saved = []
    for f in files:
        dest = UPLOAD_DIR / f.filename
        content = await f.read()
        dest.write_bytes(content)
        saved.append({"name": f.filename, "path": str(dest), "size": len(content)})
    return saved


@app.post("/api/pdf/process")
async def pdf_process(request: Request):
    """Process uploaded PDFs: remove watermarks and export PNGs."""
    body = await request.json()
    paths = body.get("paths", [])
    resolution = body.get("resolution", 3840)
    supersample = body.get("supersample", 2)
    sharpness = body.get("sharpness", 1.3)
    output_dir = body.get("output_dir", str(OUTPUT_DIR / "cleaned_pngs"))

    if not paths:
        raise HTTPException(400, "No PDF paths provided")

    from .core.pdf_cleaner import CleanerConfig, run_batch, get_pdf_page_count

    cfg = CleanerConfig(
        target_long_edge=resolution,
        supersample=supersample,
        sharpness_factor=sharpness,
    )

    total_pages = sum(get_pdf_page_count(p) for p in paths)
    job_id = f"pdf_{id(paths)}"
    _jobs[job_id] = {"status": "running", "progress": 0, "total": total_pages, "message": "Starting..."}

    async def _run():
        def on_progress(completed, total, status):
            _jobs[job_id] = {"status": "running", "progress": completed, "total": total, "message": status}

        loop = asyncio.get_event_loop()
        success, errors = await loop.run_in_executor(
            None, lambda: run_batch(paths, output_dir, cfg, progress_callback=on_progress)
        )
        _jobs[job_id] = {"status": "done", "progress": total_pages, "total": total_pages,
                         "message": f"Done! {success} pages exported, {errors} errors.",
                         "output_dir": output_dir, "success": success, "errors": errors}

    asyncio.create_task(_run())
    return {"job_id": job_id, "total_pages": total_pages}


@app.get("/api/pdf/status/{job_id}")
async def pdf_status(job_id: str):
    return _jobs.get(job_id, {"status": "not_found"})


# ------------------------------------------------------------------ #
#  Audio Transcriber API                                               #
# ------------------------------------------------------------------ #

@app.post("/api/transcribe/upload")
async def transcribe_upload(file: UploadFile = File(...)):
    """Upload an audio file for transcription."""
    dest = UPLOAD_DIR / file.filename
    content = await file.read()
    dest.write_bytes(content)
    return {"name": file.filename, "path": str(dest), "size": len(content)}


@app.post("/api/transcribe/start")
async def transcribe_start(request: Request):
    """Start transcription of an uploaded audio file."""
    body = await request.json()
    audio_path = body.get("path")
    model = body.get("model", "small")
    language = body.get("language", "en")

    if not audio_path or not os.path.isfile(audio_path):
        raise HTTPException(400, "Invalid audio file path")

    from .core.transcriber import TranscriberConfig, transcribe_audio

    cfg = TranscriberConfig(model_name=model, language=language)
    job_id = f"transcribe_{id(audio_path)}"
    _jobs[job_id] = {"status": "running", "message": "Starting transcription..."}

    async def _run():
        def on_progress(msg):
            _jobs[job_id] = {"status": "running", "message": msg}

        loop = asyncio.get_event_loop()
        try:
            result = await loop.run_in_executor(
                None, lambda: transcribe_audio(audio_path, cfg, progress_callback=on_progress)
            )
            _jobs[job_id] = {
                "status": "done",
                "message": f"Done! {len(result['text'])} chars, {len(result['segments'])} segments",
                "text": result["text"],
                "segments": result["segments"],
            }
        except Exception as e:
            _jobs[job_id] = {"status": "error", "message": str(e)}

    asyncio.create_task(_run())
    return {"job_id": job_id}


@app.get("/api/transcribe/status/{job_id}")
async def transcribe_status(job_id: str):
    return _jobs.get(job_id, {"status": "not_found"})


@app.post("/api/transcribe/split")
async def transcribe_split(request: Request):
    """Split text into parts."""
    body = await request.json()
    text = body.get("text", "")
    num_parts = body.get("num_parts", 1)
    overlap = body.get("overlap", 500)

    from .core.transcriber import split_text_into_parts
    chunks = split_text_into_parts(text, num_parts, overlap)
    return {"chunks": chunks, "count": len(chunks)}


# ------------------------------------------------------------------ #
#  NotebookLM API                                                      #
# ------------------------------------------------------------------ #

def _nlm_available():
    try:
        from . import core  # noqa
        import notebooklm  # noqa
        return True
    except ImportError:
        return False


@app.post("/api/nlm/login")
async def nlm_login():
    if not _nlm_available():
        raise HTTPException(400, "notebooklm-py not installed")
    from .core.nlm_client import login
    loop = asyncio.get_event_loop()
    try:
        await loop.run_in_executor(None, login)
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/nlm/notebooks")
async def nlm_list_notebooks():
    if not _nlm_available():
        raise HTTPException(400, "notebooklm-py not installed")
    from .core.nlm_client import list_notebooks
    try:
        nbs = await list_notebooks()
        return [{"id": nb.id, "title": nb.title, "sources_count": nb.sources_count} for nb in (nbs or [])]
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/nlm/notebooks")
async def nlm_create_notebook(request: Request):
    if not _nlm_available():
        raise HTTPException(400, "notebooklm-py not installed")
    body = await request.json()
    from .core.nlm_client import create_notebook
    try:
        nb = await create_notebook(body["title"])
        return {"id": nb.id, "title": nb.title}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.delete("/api/nlm/notebooks/{notebook_id}")
async def nlm_delete_notebook(notebook_id: str):
    if not _nlm_available():
        raise HTTPException(400, "notebooklm-py not installed")
    from .core.nlm_client import delete_notebook
    try:
        await delete_notebook(notebook_id)
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/nlm/notebooks/{notebook_id}/sources")
async def nlm_list_sources(notebook_id: str):
    if not _nlm_available():
        raise HTTPException(400, "notebooklm-py not installed")
    from .core.nlm_client import list_sources
    try:
        sources = await list_sources(notebook_id)
        return [{"id": s.id, "title": s.title or "(untitled)"} for s in (sources or [])]
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/nlm/notebooks/{notebook_id}/sources/url")
async def nlm_add_source_url(notebook_id: str, request: Request):
    if not _nlm_available():
        raise HTTPException(400, "notebooklm-py not installed")
    body = await request.json()
    from .core.nlm_client import add_source_url
    try:
        src = await add_source_url(notebook_id, body["url"])
        return {"id": src.id, "title": src.title}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/nlm/notebooks/{notebook_id}/sources/text")
async def nlm_add_source_text(notebook_id: str, request: Request):
    if not _nlm_available():
        raise HTTPException(400, "notebooklm-py not installed")
    body = await request.json()
    from .core.nlm_client import add_source_text
    try:
        src = await add_source_text(notebook_id, body["title"], body["content"])
        return {"id": src.id, "title": src.title}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/nlm/notebooks/{notebook_id}/sources/file")
async def nlm_add_source_file(notebook_id: str, file: UploadFile = File(...)):
    if not _nlm_available():
        raise HTTPException(400, "notebooklm-py not installed")
    dest = UPLOAD_DIR / file.filename
    content = await file.read()
    dest.write_bytes(content)
    from .core.nlm_client import add_source_file
    try:
        src = await add_source_file(notebook_id, str(dest))
        return {"id": src.id, "title": src.title}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.delete("/api/nlm/notebooks/{notebook_id}/sources/{source_id}")
async def nlm_delete_source(notebook_id: str, source_id: str):
    if not _nlm_available():
        raise HTTPException(400, "notebooklm-py not installed")
    from .core.nlm_client import delete_source
    try:
        await delete_source(notebook_id, source_id)
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/nlm/notebooks/{notebook_id}/artifacts")
async def nlm_list_artifacts(notebook_id: str):
    if not _nlm_available():
        raise HTTPException(400, "notebooklm-py not installed")
    from .core.nlm_client import list_artifacts
    try:
        arts = await list_artifacts(notebook_id)
        return [{"id": a.id, "title": a.title,
                 "kind": a.kind.value if hasattr(a, "kind") else "unknown",
                 "type_code": a._artifact_type if hasattr(a, "_artifact_type") else None}
                for a in (arts or [])]
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/nlm/notebooks/{notebook_id}/generate")
async def nlm_generate(notebook_id: str, request: Request):
    if not _nlm_available():
        raise HTTPException(400, "notebooklm-py not installed")
    body = await request.json()
    artifact_type = body.pop("artifact_type")

    # Convert enum string values back to enum objects if notebooklm enums available
    try:
        from notebooklm import (
            AudioFormat, AudioLength, VideoFormat, VideoStyle,
            ReportFormat, QuizQuantity, QuizDifficulty,
            InfographicOrientation, InfographicDetail, InfographicStyle,
            SlideDeckFormat, SlideDeckLength,
        )
        enum_map = {
            "audio_format": AudioFormat, "audio_length": AudioLength,
            "video_format": VideoFormat, "video_style": VideoStyle,
            "report_format": ReportFormat,
            "quantity": QuizQuantity, "difficulty": QuizDifficulty,
            "orientation": InfographicOrientation, "detail_level": InfographicDetail,
            "style": InfographicStyle,
            "slide_format": SlideDeckFormat, "slide_length": SlideDeckLength,
        }
        for key, enum_cls in enum_map.items():
            if key in body and isinstance(body[key], (int, str)):
                try:
                    body[key] = enum_cls(body[key])
                except (ValueError, KeyError):
                    pass
    except ImportError:
        pass

    from .core.nlm_client import generate_artifact
    try:
        result = await generate_artifact(notebook_id, artifact_type, body)
        return {"status": "ok", "title": getattr(result, "title", "Generated")}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/nlm/notebooks/{notebook_id}/download")
async def nlm_download(notebook_id: str, request: Request):
    if not _nlm_available():
        raise HTTPException(400, "notebooklm-py not installed")
    body = await request.json()
    artifact_type = body.get("artifact_type", "report")
    artifact_id = body.get("artifact_id")
    ext_map = {"audio": ".mp3", "video": ".mp4", "report": ".md", "quiz": ".json",
               "flashcards": ".json", "infographic": ".png", "slide_deck": ".pdf",
               "data_table": ".md", "mind_map": ".md"}
    ext = ext_map.get(artifact_type, ".bin")
    output_path = str(OUTPUT_DIR / f"download_{artifact_id or 'latest'}{ext}")

    from .core.nlm_client import download_artifact
    try:
        await download_artifact(notebook_id, artifact_type, output_path, artifact_id=artifact_id)
        return FileResponse(output_path, filename=f"artifact{ext}")
    except Exception as e:
        raise HTTPException(500, str(e))


@app.delete("/api/nlm/notebooks/{notebook_id}/artifacts/{artifact_id}")
async def nlm_delete_artifact(notebook_id: str, artifact_id: str):
    if not _nlm_available():
        raise HTTPException(400, "notebooklm-py not installed")
    from .core.nlm_client import delete_artifact
    try:
        await delete_artifact(notebook_id, artifact_id)
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/nlm/notebooks/{notebook_id}/chat")
async def nlm_chat(notebook_id: str, request: Request):
    if not _nlm_available():
        raise HTTPException(400, "notebooklm-py not installed")
    body = await request.json()
    from .core.nlm_client import chat_ask
    try:
        result = await chat_ask(
            notebook_id, body["question"],
            source_ids=body.get("source_ids"),
            conversation_id=body.get("conversation_id"),
        )
        refs = []
        if result.references:
            for ref in result.references:
                refs.append({
                    "citation_number": ref.citation_number,
                    "cited_text": (ref.cited_text or "")[:200],
                })
        return {
            "answer": result.answer,
            "conversation_id": result.conversation_id,
            "references": refs,
        }
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/nlm/notebooks/{notebook_id}/chat/mode")
async def nlm_set_chat_mode(notebook_id: str, request: Request):
    if not _nlm_available():
        raise HTTPException(400, "notebooklm-py not installed")
    body = await request.json()
    from .core.nlm_client import configure_chat
    try:
        await configure_chat(notebook_id, mode=body.get("mode"))
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(500, str(e))


# ------------------------------------------------------------------ #
#  Saved Prompts (persisted to JSON file)                              #
# ------------------------------------------------------------------ #

PROMPTS_FILE = Path(__file__).parent / "saved_prompts.json"


def _load_prompts():
    if PROMPTS_FILE.exists():
        try:
            return json.loads(PROMPTS_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_prompts(data):
    PROMPTS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


@app.get("/api/prompts")
async def get_prompts():
    return _load_prompts()


@app.post("/api/prompts")
async def save_prompt(request: Request):
    body = await request.json()
    prompts = _load_prompts()
    prompts[body["name"]] = body["text"]
    _save_prompts(prompts)
    return {"status": "ok"}


@app.delete("/api/prompts/{name}")
async def delete_prompt(name: str):
    prompts = _load_prompts()
    prompts.pop(name, None)
    _save_prompts(prompts)
    return {"status": "ok"}


# ------------------------------------------------------------------ #
#  Start server                                                        #
# ------------------------------------------------------------------ #

def start(host="127.0.0.1", port=8000):
    import uvicorn
    import webbrowser
    import threading

    def open_browser():
        import time
        time.sleep(1.5)
        webbrowser.open(f"http://{host}:{port}")

    threading.Thread(target=open_browser, daemon=True).start()

    print(f"\n  NotebookLM Toolkit v2.0")
    print(f"  Running at http://{host}:{port}")
    print(f"  Press Ctrl+C to stop\n")

    uvicorn.run(app, host=host, port=port, log_level="warning")
