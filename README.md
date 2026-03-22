# NotebookLM Toolkit

A web-based toolkit for Google's NotebookLM. Manage notebooks, transcribe audio, and clean PDFs — all from your browser.

![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue)

## Features

- **NotebookLM Client** — Create/manage notebooks, upload sources, generate all 9 artifact types (audio, video, reports, quizzes, flashcards, infographics, slide decks, data tables, mind maps), chat with your sources
- **Audio Transcriber** — Transcribe audio to text using faster-whisper (runs locally, no API key needed). Split transcripts into parts with overlap for uploading to NotebookLM
- **PDF Cleaner** — Remove NotebookLM watermarks and export pages as high-resolution 4K PNGs

## Quick Start

### Option 1: pip install (recommended)

```bash
pip install notebooklm-toolkit
notebooklm-toolkit
```

Opens in your browser at http://localhost:8000.

### Option 2: From source

```bash
git clone https://github.com/RyanPiao/notebooklm-toolkit.git
cd notebooklm-toolkit
pip install -e .
notebooklm-toolkit
```

### Option 3: Docker

```bash
docker build -t notebooklm-toolkit .
docker run -p 8000:8000 notebooklm-toolkit
```

## Optional Extras

### GPU acceleration (faster transcription)

```bash
# NVIDIA GPU
pip install notebooklm-toolkit[gpu] --extra-index-url https://download.pytorch.org/whl/cu128

# Apple Silicon — just install torch
pip install torch torchvision torchaudio
```

### NotebookLM integration

```bash
pip install notebooklm-toolkit[nlm]
playwright install chromium
```

### Everything at once

```bash
pip install notebooklm-toolkit[all]
playwright install chromium
```

## How It Works

The toolkit runs a local web server (FastAPI) and serves a modern dashboard UI in your browser. No system dependencies required — faster-whisper bundles its own audio decoder, and the browser handles audio playback natively.

### Architecture

```
Browser (localhost:8000)
    ↕ REST API
FastAPI Server
    ├── Audio Transcriber (faster-whisper, local)
    ├── PDF Cleaner (PyMuPDF + OpenCV)
    └── NotebookLM Client (notebooklm-py, optional)
```

## Transcription Performance

| Setup | 50-min audio, `small` model |
|-------|---------------------------|
| CPU only | 15-30 minutes |
| Apple Silicon | 5-10 minutes |
| NVIDIA GPU (CUDA) | 2-5 minutes |

## Legacy GUI

The previous tkinter-based GUI (`app_gui.py`) is still available in the repo for backward compatibility:

```bash
pip install -r requirements.txt
python app_gui.py
```

## License

MIT
