#!/usr/bin/env python3
"""
Audio Transcriber — Core Engine

Transcribes .m4a audio files to text using OpenAI Whisper (local),
with option to split output by character count.
"""

import os
import whisper
import textwrap
from dataclasses import dataclass
from typing import Optional, Callable, List


# ------------------------------------------------------------------ #
#  Configuration                                                      #
# ------------------------------------------------------------------ #

# Recommended models for different audio lengths:
#   tiny   — fastest, least accurate, good for testing
#   base   — fast, OK for short clear audio
#   small  — best balance for 40-50 min audio (~80MB m4a)
#   medium — more accurate, significantly slower
#   large  — most accurate, very slow, needs GPU
AVAILABLE_MODELS = ["tiny", "base", "small", "medium", "large"]

@dataclass
class TranscriberConfig:
    """Configuration for audio transcription."""
    model_name: str = "small"    # best for 40-50 min audio
    language: str = "en"
    split_chars: int = 0         # 0 = no splitting


# ------------------------------------------------------------------ #
#  Text splitting                                                     #
# ------------------------------------------------------------------ #

def split_text_by_chars(text: str, max_chars: int) -> List[str]:
    """
    Split text into chunks of approximately max_chars characters.
    Splits at word boundaries to avoid cutting words.
    """
    if max_chars <= 0 or len(text) <= max_chars:
        return [text]

    chunks = []
    remaining = text.strip()

    while remaining:
        if len(remaining) <= max_chars:
            chunks.append(remaining)
            break

        # Find the last space within the limit
        split_pos = remaining.rfind(" ", 0, max_chars)
        if split_pos == -1:
            # No space found — force split at max_chars
            split_pos = max_chars

        chunk = remaining[:split_pos].strip()
        if chunk:
            chunks.append(chunk)
        remaining = remaining[split_pos:].strip()

    return chunks


# ------------------------------------------------------------------ #
#  Transcription                                                      #
# ------------------------------------------------------------------ #

def transcribe_audio(
    audio_path: str,
    cfg: TranscriberConfig,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> dict:
    """
    Transcribe an m4a audio file using local Whisper.

    Args:
        audio_path: Path to the .m4a file.
        cfg: Transcription configuration.
        progress_callback: Called with status messages.

    Returns:
        dict with keys:
            "text": full transcribed text
            "chunks": list of text chunks (if split_chars > 0, else [full_text])
            "segments": list of {start, end, text} dicts from Whisper
    """
    if not os.path.isfile(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    ext = os.path.splitext(audio_path)[1].lower()
    if ext != ".m4a":
        raise ValueError(f"Unsupported format: {ext}. Only .m4a is supported.")

    if progress_callback:
        progress_callback(f"Loading Whisper '{cfg.model_name}' model...")

    model = whisper.load_model(cfg.model_name)

    if progress_callback:
        progress_callback("Transcribing audio (this may take several minutes)...")

    result = model.transcribe(
        audio_path,
        language=cfg.language,
        verbose=False,
    )

    full_text = result["text"].strip()

    # Build segments list
    segments = []
    for seg in result.get("segments", []):
        segments.append({
            "start": seg["start"],
            "end": seg["end"],
            "text": seg["text"].strip(),
        })

    # Split text if requested
    if cfg.split_chars > 0:
        chunks = split_text_by_chars(full_text, cfg.split_chars)
    else:
        chunks = [full_text]

    if progress_callback:
        progress_callback(
            f"Done! {len(full_text)} chars, {len(segments)} segments, {len(chunks)} chunk(s)"
        )

    return {
        "text": full_text,
        "chunks": chunks,
        "segments": segments,
    }


def save_transcription(
    result: dict,
    output_path: str,
    split_chars: int = 0,
) -> List[str]:
    """
    Save transcription result to file(s).

    If split_chars > 0, saves multiple files: output_001.txt, output_002.txt, etc.
    Otherwise saves a single file.

    Returns list of saved file paths.
    """
    saved = []
    base, ext = os.path.splitext(output_path)
    if not ext:
        ext = ".txt"

    if split_chars > 0 and len(result["chunks"]) > 1:
        for i, chunk in enumerate(result["chunks"], 1):
            chunk_path = f"{base}_{i:03d}{ext}"
            with open(chunk_path, "w", encoding="utf-8") as f:
                f.write(chunk)
            saved.append(chunk_path)
    else:
        with open(f"{base}{ext}", "w", encoding="utf-8") as f:
            f.write(result["text"])
        saved.append(f"{base}{ext}")

    return saved


# ------------------------------------------------------------------ #
#  CLI                                                                #
# ------------------------------------------------------------------ #

def cli_main():
    """Command-line interface for audio transcription."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Audio Transcriber - Transcribe .m4a files using local Whisper"
    )
    parser.add_argument("audio", help="Path to .m4a audio file")
    parser.add_argument(
        "-o", "--output", default=None,
        help="Output text file path (default: same name as input with .txt)",
    )
    parser.add_argument(
        "--model", choices=AVAILABLE_MODELS, default="small",
        help="Whisper model size (default: small)",
    )
    parser.add_argument(
        "--language", default="en",
        help="Audio language (default: en)",
    )
    parser.add_argument(
        "--split", type=int, default=0,
        help="Split output text by N characters (default: 0 = no split)",
    )

    args = parser.parse_args()

    cfg = TranscriberConfig(
        model_name=args.model,
        language=args.language,
        split_chars=args.split,
    )

    if args.output is None:
        base = os.path.splitext(args.audio)[0]
        args.output = f"{base}.txt"

    print(f"Input:    {args.audio}")
    print(f"Model:    {cfg.model_name}")
    print(f"Language: {cfg.language}")
    if cfg.split_chars > 0:
        print(f"Split:    every {cfg.split_chars} chars")
    print()

    def on_status(msg):
        print(f"  {msg}")

    result = transcribe_audio(args.audio, cfg, progress_callback=on_status)

    saved = save_transcription(result, args.output, cfg.split_chars)

    print(f"\nTranscription saved to:")
    for p in saved:
        print(f"  {p}")
    print(f"\nTotal: {len(result['text'])} characters, {len(result['segments'])} segments")


if __name__ == "__main__":
    cli_main()
