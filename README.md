# NotebookLM Toolkit

An all-in-one Python toolkit for Google NotebookLM. Three tools in one app:

1. **PDF Cleaner** — Remove watermarks from NotebookLM PDFs and export as 4K PNGs
2. **Audio Transcriber** — Convert `.m4a` audio to text using local Whisper AI
3. **NotebookLM Client** — Control NotebookLM directly: create notebooks, add sources, generate content, chat

Works on **macOS** and **Windows**. GUI + CLI.

---

## Quick Start

### macOS

```bash
# 1. Install FFmpeg (needed for audio transcription)
brew install ffmpeg

# 2. Clone and set up
git clone https://github.com/RyanPiao/notebooklm-toolkit.git
cd notebooklm-toolkit
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 3. (Optional) NotebookLM integration
pip install "notebooklm-py[browser]"
playwright install chromium

# 4. Run
python app_gui.py
```

### Windows

```powershell
# 1. Install FFmpeg
#    Download from https://ffmpeg.org/download.html (get "essentials" build)
#    Extract the zip, add the bin folder to your system PATH
#    Verify: ffmpeg -version

# 2. Clone and set up
git clone https://github.com/RyanPiao/notebooklm-toolkit.git
cd notebooklm-toolkit
python -m venv venv
venv\Scripts\pip.exe install -r requirements.txt

# 3. (Optional) NotebookLM integration
venv\Scripts\pip.exe install "notebooklm-py[browser]"
venv\Scripts\python.exe -m playwright install chromium

# 4. Run
venv\Scripts\python.exe app_gui.py
```

> **Note:** If `venv\Scripts\activate` doesn't work in PowerShell, run:
> `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned`
> Or just use `venv\Scripts\python.exe` directly as shown above.

---

## Features

### Tab 1: PDF Cleaner

Removes the "NotebookLM" watermark from exported PDFs and saves each page as a high-resolution PNG.

**How it works:**
1. Detects the watermark using text search + pixel-based detection
2. Removes it with OpenCV inpainting (reconstructs the background — not a cover-up)
3. Renders each page at 2x the target resolution (supersample)
4. Downscales with Lanczos for sharp, anti-aliased output
5. Applies mild sharpening for crisp text

**GUI:** Select PDFs or a folder → choose output folder → set resolution → click Start

**CLI:**
```bash
# Single PDF → 4K PNGs
python pdf_cleaner_core.py slides.pdf

# Folder of PDFs with custom settings
python pdf_cleaner_core.py ./my_pdfs/ -o ./output --resolution 3840 --supersample 2

# All options
python pdf_cleaner_core.py input.pdf -o output \
    --resolution 3840 \
    --supersample 2 \
    --sharpness 1.3 \
    --workers 4 \
    --margin-x 300 \
    --margin-y 65
```

| Option | Default | Description |
|--------|---------|-------------|
| `-o, --output` | `cleaned_pngs` | Output directory |
| `--resolution` | `3840` | Long-edge pixels (1920 / 2560 / 3840 / 5120) |
| `--supersample` | `2` | Render at Nx, downscale with Lanczos |
| `--sharpness` | `1.3` | Sharpness factor (1.0 = off) |
| `--workers` | auto | Parallel workers (default: min of CPU count, 4) |
| `--margin-x` | `300` | Watermark search area from right edge (px) |
| `--margin-y` | `65` | Watermark search area from bottom edge (px) |

---

### Tab 2: Audio Transcriber

Converts `.m4a` audio files to text using [OpenAI Whisper](https://github.com/openai/whisper) running 100% locally. No cloud API, no Docker, no internet needed (after first model download).

**Key feature: split after transcription.** Transcribe first, then decide how to split:
- Split into N equal parts (e.g., "split into 3") — the app calculates chunk sizes automatically
- Each part from 2 onward includes a configurable overlap (default 500 chars) from the previous part for context continuity
- Navigate chunks in the GUI, copy individual parts to clipboard

**GUI:** Select `.m4a` file → pick Whisper model → click Transcribe → adjust split settings → copy or save

**CLI:**
```bash
# Basic transcription
python audio_transcriber.py lecture.m4a

# Split into 3 equal parts with 500-char overlap
python audio_transcriber.py lecture.m4a --split-parts 3 --overlap 500

# Split by max character count
python audio_transcriber.py lecture.m4a --split-chars 2000

# Different model and language
python audio_transcriber.py lecture.m4a --model medium --language zh

# Custom output
python audio_transcriber.py lecture.m4a -o transcript.txt --split-parts 4
```

| Option | Default | Description |
|--------|---------|-------------|
| `-o, --output` | `<input_name>.txt` | Output file path |
| `--model` | `small` | Whisper model (see table below) |
| `--language` | `en` | Audio language code |
| `--split-parts` | `0` | Split into N equal parts |
| `--split-chars` | `0` | Split every N characters |
| `--overlap` | `500` | Overlap chars from previous part (0 = off) |

`--split-parts` and `--split-chars` are mutually exclusive. Split files are named `transcript_001.txt`, `transcript_002.txt`, etc.

**Whisper Model Guide:**

| Model | Download | Speed | Accuracy | Best for |
|-------|----------|-------|----------|----------|
| `tiny` | 39 MB | Fastest | Low | Quick tests |
| `base` | 74 MB | Fast | OK | Short, clear audio |
| **`small`** | **244 MB** | **Moderate** | **Good** | **40–50 min recordings (default)** |
| `medium` | 769 MB | Slow | High | When accuracy matters |
| `large` | 1.5 GB | Slowest | Best | Max accuracy, GPU recommended |

Models download automatically on first use and are cached locally.

---

### Tab 3: NotebookLM Client (Optional)

Control Google NotebookLM directly from the app. Powered by [notebooklm-py](https://github.com/teng-lin/notebooklm-py).

> **Requires:** `pip install "notebooklm-py[browser]"` + `playwright install chromium`
> The tab only appears if `notebooklm-py` is installed. All other features work without it.

#### First Time Setup

1. Click **"Login (Browser)"** — a Chromium window opens
2. Sign in with your Google account that has NotebookLM access
3. Close the browser when done — cookies are saved to `~/.notebooklm/`
4. Click **"List"** to load your notebooks

Cookies expire periodically — re-login when needed.

#### What You Can Do

**Manage Notebooks:**
- Create, list, and delete notebooks
- Click a notebook to load its sources and artifacts

**Manage Sources:**
- Add web URLs or YouTube links
- Upload files (PDF, DOCX, Markdown, CSV, TXT)
- Add pasted text with a title
- Delete sources

**Generate Artifacts** — 9 types with full parameter control:

| Artifact | Parameters |
|----------|-----------|
| **Audio Overview** | Format: Deep Dive / Brief / Critique / Debate | Length: Short / Default / Long | Language |
| **Video** | Format: Explainer / Brief / Cinematic | Style: Auto / Classic / Whiteboard / Kawaii / Anime / Watercolor / Retro Print / Heritage / Paper Craft / Custom | Language |
| **Report** | Format: Briefing Doc / Study Guide / Blog Post / Custom | Language |
| **Quiz** | Quantity: Fewer / Standard / More | Difficulty: Easy / Medium / Hard |
| **Flashcards** | Quantity: Fewer / Standard / More | Difficulty: Easy / Medium / Hard |
| **Infographic** | Orientation: Landscape / Portrait / Square | Detail: Concise / Standard / Detailed | Style: Auto / Sketch Note / Professional / Bento Grid / Editorial / Instructional / Bricks / Clay / Anime / Kawaii / Scientific | Language |
| **Slide Deck** | Format: Detailed Deck / Presenter Slides | Length: Default / Short | Language |
| **Data Table** | Language |
| **Mind Map** | *(no extra parameters)* |

All artifact types accept an optional **Instructions** text field for custom prompts.
Select specific sources in the source list to scope generation to those sources only.

**Chat:**
- Ask questions about your sources with full citation references
- Chat modes: Default / Learning Guide / Concise / Detailed
- Follow-up conversations (maintains context)
- Select specific sources to focus the chat

**Download:**
- Download any generated artifact to a local file
- Optional auto-process: downloaded slide deck PDFs can be cleaned and exported as 4K PNGs via the PDF Cleaner tab

---

## GPU Acceleration (Optional)

Whisper runs on CPU by default. Adding GPU support speeds up transcription significantly — **no code changes needed**, the app detects your GPU automatically and shows which device it's using.

| Setup | ~Time for 50 min audio (`small` model) |
|-------|---------------------------------------|
| CPU only | 15–30 min |
| Apple Silicon (M1/M2/M3/M4) | 5–10 min |
| NVIDIA GPU (CUDA) | 2–5 min |

### macOS (Apple Silicon)

```bash
pip install torch torchvision torchaudio
```

Metal (MPS) acceleration is used automatically.

### Windows / Linux (NVIDIA GPU)

Check your CUDA version with `nvidia-smi`, then install the matching PyTorch:

```bash
# CUDA 12.8
pip install --force-reinstall torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128

# CUDA 12.6
pip install --force-reinstall torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu126
```

> **Important:** You must use `--force-reinstall` because `pip install openai-whisper` installs CPU-only PyTorch as a dependency. Without this flag, pip skips the CUDA version since PyTorch is already installed.

> If these URLs stop working, check [pytorch.org/get-started/locally](https://pytorch.org/get-started/locally/) for the latest commands.

**Verify GPU is detected:**
```bash
python -c "import torch; print('CUDA:', torch.cuda.is_available()); print('MPS:', torch.backends.mps.is_available())"
```

---

## Project Structure

```
notebooklm-toolkit/
├── app_gui.py              # GUI entry point (tkinter, 3 tabs)
├── pdf_cleaner_core.py     # PDF watermark removal + 4K PNG export (GUI + CLI)
├── audio_transcriber.py    # Whisper transcription + text splitting (GUI + CLI)
├── notebooklm_tab.py       # NotebookLM GUI tab
├── notebooklm_wrapper.py   # Async-to-sync bridge for notebooklm-py
├── requirements.txt        # Core dependencies
└── README.md
```

## Dependencies

**Core (required):**
- [PyMuPDF](https://pymupdf.readthedocs.io/) — PDF rendering
- [OpenCV](https://opencv.org/) — watermark detection and inpainting
- [Pillow](https://pillow.readthedocs.io/) — image processing
- [NumPy](https://numpy.org/) — array operations
- [OpenAI Whisper](https://github.com/openai/whisper) — speech-to-text

**Optional:**
- [notebooklm-py](https://github.com/teng-lin/notebooklm-py) — NotebookLM API client
- [Playwright](https://playwright.dev/) — browser automation for NotebookLM login
- [PyTorch with CUDA/MPS](https://pytorch.org/) — GPU acceleration for Whisper

## License

MIT
