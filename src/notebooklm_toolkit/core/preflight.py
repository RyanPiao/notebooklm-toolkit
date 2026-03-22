"""
Preflight dependency checker.

Returns a status dict for each capability so the web UI
can show green/yellow/red indicators.
"""

import shutil
import importlib


def check_all():
    """Return list of {name, status, detail} dicts."""
    checks = []

    # faster-whisper
    try:
        importlib.import_module("faster_whisper")
        checks.append({"name": "Audio Transcriber", "status": "ok",
                        "detail": "faster-whisper installed"})
    except ImportError:
        checks.append({"name": "Audio Transcriber", "status": "error",
                        "detail": "Install: pip install faster-whisper"})

    # GPU detection
    try:
        import torch
        if torch.cuda.is_available():
            gpu = torch.cuda.get_device_name(0)
            checks.append({"name": "GPU Acceleration", "status": "ok",
                            "detail": f"CUDA: {gpu}"})
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            checks.append({"name": "GPU Acceleration", "status": "ok",
                            "detail": "Apple Silicon (MPS) — note: faster-whisper uses CPU"})
        else:
            checks.append({"name": "GPU Acceleration", "status": "warn",
                            "detail": "No GPU detected, transcription will use CPU (slower)"})
    except ImportError:
        checks.append({"name": "GPU Acceleration", "status": "warn",
                        "detail": "PyTorch not installed — CPU only"})

    # PDF cleaner deps
    try:
        importlib.import_module("fitz")
        importlib.import_module("cv2")
        checks.append({"name": "PDF Cleaner", "status": "ok",
                        "detail": "PyMuPDF + OpenCV installed"})
    except ImportError as e:
        checks.append({"name": "PDF Cleaner", "status": "error",
                        "detail": f"Missing: {e.name}"})

    # NotebookLM client
    try:
        importlib.import_module("notebooklm")
        checks.append({"name": "NotebookLM Client", "status": "ok",
                        "detail": "notebooklm-py installed"})
    except ImportError:
        checks.append({"name": "NotebookLM Client", "status": "warn",
                        "detail": "Optional: pip install \"notebooklm-py[browser]\""})

    # Playwright
    try:
        importlib.import_module("playwright")
        checks.append({"name": "Browser Login", "status": "ok",
                        "detail": "Playwright installed"})
    except ImportError:
        checks.append({"name": "Browser Login", "status": "warn",
                        "detail": "Optional: pip install playwright && playwright install chromium"})

    return checks
