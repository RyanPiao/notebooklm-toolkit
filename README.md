# NotebookLM Toolkit

A Python app that removes NotebookLM watermarks from PDFs and exports pages as high-quality 4K PNGs. Also includes an audio transcriber that converts `.m4a` files to text using local Whisper.

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
- Split output text by character count (useful for pasting into tools with limits)
- Chunk navigation in GUI with copy-to-clipboard support
- Selectable Whisper model: `tiny`, `base`, `small`, `medium`, `large`

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
git clone https://github.com/YOUR_USERNAME/notebooklm-toolkit.git
cd notebooklm-toolkit

# Create a virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate        # macOS / Linux
# venv\Scripts\activate         # Windows

# Install dependencies
pip install -r requirements.txt
```

## Usage

### GUI Mode

```bash
python app_gui.py
```

Opens a window with two tabs:

- **PDF Cleaner** — select PDFs or a folder, set output directory and resolution, click Start
- **Audio Transcriber** — select an `.m4a` file, choose model and split settings, click Transcribe

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

# With text splitting (every 2000 characters)
python audio_transcriber.py recording.m4a --split 2000

# Use a different model
python audio_transcriber.py recording.m4a --model medium

# Custom output path
python audio_transcriber.py recording.m4a -o transcript.txt --split 3000
```

**Options:**
| Flag | Default | Description |
|------|---------|-------------|
| `-o, --output` | `<input_name>.txt` | Output file path |
| `--model` | `small` | Whisper model (`tiny`, `base`, `small`, `medium`, `large`) |
| `--language` | `en` | Audio language code |
| `--split` | `0` | Split text every N characters (0 = no split) |

When `--split` is used, output files are named `transcript_001.txt`, `transcript_002.txt`, etc.

## Whisper Model Guide

| Model | Size | Speed | Accuracy | Recommended for |
|-------|------|-------|----------|----------------|
| `tiny` | 39 MB | Fastest | Low | Quick tests |
| `base` | 74 MB | Fast | OK | Short, clear audio |
| `small` | 244 MB | Moderate | Good | **40–50 min recordings (default)** |
| `medium` | 769 MB | Slow | High | When accuracy matters more than speed |
| `large` | 1.5 GB | Slowest | Best | Maximum accuracy, GPU recommended |

The model is downloaded automatically on first use and cached locally.

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
