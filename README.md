# NotebookLM Toolkit

An all-in-one Python toolkit for Google NotebookLM. Clean watermarks from exported PDFs, export 4K PNGs, transcribe audio to text, and control NotebookLM directly from a GUI — create notebooks, add sources, generate artifacts, and chat.

Works on **macOS** and **Windows**. Includes both a GUI and CLI.

## Features

### PDF Cleaner
- Removes NotebookLM watermarks using smart OpenCV inpainting (not a simple cover-up)
- Exports each page as a high-resolution PNG (up to 4K / 5K)
- Supersample rendering with Lanczos downscale for sharp output
- Batch processing with multiprocessing for speed
- Configurable resolution, sharpness, and watermark margins

### Audio Transcriber
- Transcribes `.m4a` audio to text using [OpenAI Whisper](https://github.com/openai/whisper) running locally (no cloud API, no Docker)
- Best suited for 40–50 minute recordings (~80 MB files) with the `small` model
- Split text **after** transcription into N equal parts (e.g., split into 2, 3, 4 parts)
- Also supports splitting by max character count via CLI
- Chunk navigation in GUI with copy-to-clipboard per part
- Selectable Whisper model: `tiny`, `base`, `small`, `medium`, `large`

### NotebookLM Client (Optional)
Powered by [notebooklm-py](https://github.com/teng-lin/notebooklm-py) — an unofficial Python client for Google NotebookLM.

- **Notebook management** — create, list, delete notebooks
- **Source management** — add URLs, files (PDF/DOCX/MD/CSV), text, YouTube links; delete sources
- **Generate artifacts** with full parameter control:
  - **Audio Overview** — format (Deep Dive / Brief / Critique / Debate), length (Short / Default / Long), language
  - **Video** — format (Explainer / Brief / Cinematic), style (10 options including Anime, Watercolor, Whiteboard), language
  - **Report** — format (Briefing Doc / Study Guide / Blog Post / Custom), language
  - **Quiz** — quantity (Fewer / Standard / More), difficulty (Easy / Medium / Hard)
  - **Flashcards** — quantity, difficulty
  - **Infographic** — orientation (Landscape / Portrait / Square), detail (Concise / Standard / Detailed), style (11 options), language
  - **Slide Deck** — format (Detailed Deck / Presenter Slides), length (Default / Short), language
  - **Data Table** — language
  - **Mind Map**
- **Chat** — ask questions with citations, select chat mode (Default / Learning Guide / Concise / Detailed), follow-up conversations
- **Download** artifacts with optional auto-processing (clean PDF → 4K PNGs, audio → transcription)

## Installation

### Prerequisites

- **Python 3.9+** — [python.org](https://www.python.org/downloads/)
- **FFmpeg** — required by Whisper for audio decoding

#### Install FFmpeg

**macOS:**
```bash
brew install ffmpeg
```

**Windows:**
1. Download from [ffmpeg.org/download.html](https://ffmpeg.org/download.html) (get the "essentials" build)
2. Extract the zip and add the `bin` folder to your system PATH
3. Verify: `ffmpeg -version`

### Install the app

```bash
# Clone the repo
git clone https://github.com/RyanPiao/notebooklm-toolkit.git
cd notebooklm-toolkit

# Create a virtual environment (recommended)
python3 -m venv venv
# source venv/bin/activate        # macOS / Linux
# venv\Scripts\activate         # Windows

# Install dependencies
pip install -r requirements.txt

# Optional: Enable NotebookLM integration
pip install "notebooklm-py[browser]"
playwright install chromium
```

## Usage

### GUI Mode

```bash
python app_gui.py
```

Opens a window with tabs:

- **PDF Cleaner** — select PDFs or a folder, set output directory and resolution, click Start
- **Audio Transcriber** — select an `.m4a` file, choose model and split settings, click Transcribe
- **NotebookLM** *(if notebooklm-py installed)* — manage notebooks, sources, generate artifacts, chat

#### NotebookLM Tab — First Time Setup

1. Click **"Login (Browser)"** — opens a Chromium window for Google sign-in
2. Sign in with your Google account that has NotebookLM access
3. Close the browser when prompted — cookies are saved locally
4. Click **"List"** to load your notebooks

Authentication cookies expire periodically — re-login when needed.

### CLI Mode

#### PDF Cleaner

```bash
# Single PDF
python pdf_cleaner_core.py input.pdf

# Folder of PDFs
python pdf_cleaner_core.py ./my_pdfs/ -o ./output_pngs

# Custom resolution and settings
python pdf_cleaner_core.py input.pdf -o output --resolution 3840 --supersample 2 --sharpness 1.3
```

**Options:**
| Flag | Default | Description |
|------|---------|-------------|
| `-o, --output` | `cleaned_pngs` | Output directory |
| `--resolution` | `3840` | Long-edge pixels (1920, 2560, 3840, 5120) |
| `--supersample` | `2` | Render at Nx then downscale with Lanczos |
| `--sharpness` | `1.3` | Sharpness factor (1.0 = no change) |
| `--workers` | auto | Max parallel workers |
| `--margin-x` | `300` | Watermark search margin from right edge (px) |
| `--margin-y` | `65` | Watermark search margin from bottom edge (px) |

#### Audio Transcriber

```bash
# Basic transcription
python audio_transcriber.py recording.m4a

# Split into 3 equal parts
python audio_transcriber.py recording.m4a --split-parts 3

# Split by max character count
python audio_transcriber.py recording.m4a --split-chars 2000

# Use a different model
python audio_transcriber.py recording.m4a --model medium

# Custom output path
python audio_transcriber.py recording.m4a -o transcript.txt --split-parts 4
```

**Options:**
| Flag | Default | Description |
|------|---------|-------------|
| `-o, --output` | `<input_name>.txt` | Output file path |
| `--model` | `small` | Whisper model (`tiny`, `base`, `small`, `medium`, `large`) |
| `--language` | `en` | Audio language code |
| `--split-parts` | `0` | Split into N equal parts (e.g., `3` = three ~equal chunks) |
| `--split-chars` | `0` | Split every N characters (e.g., `2000`) |

`--split-parts` and `--split-chars` are mutually exclusive. When either is used, output files are named `transcript_001.txt`, `transcript_002.txt`, etc.

## Whisper Model Guide

| Model | Size | Speed | Accuracy | Recommended for |
|-------|------|-------|----------|----------------|
| `tiny` | 39 MB | Fastest | Low | Quick tests |
| `base` | 74 MB | Fast | OK | Short, clear audio |
| `small` | 244 MB | Moderate | Good | **40–50 min recordings (default)** |
| `medium` | 769 MB | Slow | High | When accuracy matters more than speed |
| `large` | 1.5 GB | Slowest | Best | Maximum accuracy, GPU recommended |

The model is downloaded automatically on first use and cached locally.

## GPU Acceleration (Optional)

Whisper runs on CPU by default. Installing PyTorch with GPU support significantly speeds up transcription — no code changes needed, Whisper detects GPU automatically.

### Speed comparison (50 min audio, `small` model)

| Setup | Approximate time |
|-------|-----------------|
| CPU only | 15–30 min |
| Apple Silicon (M1/M2/M3/M4) | 5–10 min |
| NVIDIA GPU (CUDA) | 2–5 min |

### macOS (Apple Silicon)

PyTorch uses Metal (MPS) acceleration automatically:

```bash
pip install torch torchvision torchaudio
```

### Windows / Linux with NVIDIA GPU

Install PyTorch with CUDA support. Pick the command matching your CUDA version (check with `nvidia-smi`):

**CUDA 12.8:**
```bash
pip install --force-reinstall torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128
```

**CUDA 12.6:**
```bash
pip install --force-reinstall torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu126
```

> **Important:** Use `--force-reinstall` because `pip install openai-whisper` pulls in CPU-only torch as a dependency. Without `--force-reinstall`, pip may skip the CUDA version since torch is already installed.

> Check [pytorch.org/get-started/locally](https://pytorch.org/get-started/locally/) for the latest install commands if the above URLs stop working.

### Verify GPU is detected

```python
import torch
print(torch.cuda.is_available())              # True = NVIDIA GPU
print(torch.backends.mps.is_available())      # True = Apple Silicon
```

## How It Works

### PDF Cleaner Pipeline
1. **Detect watermark** — searches for "NotebookLM" text in the PDF; falls back to pixel-based detection in the bottom-right corner
2. **Remove watermark** — uses OpenCV inpainting (TELEA algorithm) to reconstruct the background behind the watermark
3. **Render at high DPI** — renders the cleaned page at 2x the target resolution
4. **Downscale with Lanczos** — produces sharp, anti-aliased output at exact 4K dimensions
5. **Sharpen** — applies mild sharpening for crisp text

### Audio Transcriber Pipeline
1. **Load Whisper model** locally (no internet needed after first download)
2. **Transcribe** the `.m4a` file with timestamps
3. **Split** the output text by character count at word boundaries
4. **Save** to one or multiple text files

## Dependencies

- [PyMuPDF](https://pymupdf.readthedocs.io/) — PDF rendering and manipulation
- [OpenCV](https://opencv.org/) — watermark detection and inpainting
- [Pillow](https://pillow.readthedocs.io/) — image processing and Lanczos downscale
- [NumPy](https://numpy.org/) — array operations
- [OpenAI Whisper](https://github.com/openai/whisper) — local speech-to-text

## License

MIT
