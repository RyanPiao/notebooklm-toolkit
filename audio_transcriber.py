#!/usr/bin/env python3
"""
Audio Transcriber — Core Engine

Transcribes .m4a audio files to text using OpenAI Whisper (local),
with option to split output into equal parts after transcription.
"""

import os
import math
import whisper
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

        split_pos = remaining.rfind(" ", 0, max_chars)
        if split_pos == -1:
            split_pos = max_chars

        chunk = remaining[:split_pos].strip()
        if chunk:
            chunks.append(chunk)
        remaining = remaining[split_pos:].strip()

    return chunks


def split_text_into_parts(text: str, num_parts: int) -> List[str]:
    """
    Split text into N roughly equal parts at word boundaries.
    """
    if num_parts <= 1 or not text.strip():
        return [text.strip()]

    chars_per_part = math.ceil(len(text.strip()) / num_parts)
    return split_text_by_chars(text, chars_per_part)


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

    Returns:
        dict with keys:
            "text": full transcribed text
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

    segments = []
    for seg in result.get("segments", []):
        segments.append({
            "start": seg["start"],
            "end": seg["end"],
            "text": seg["text"].strip(),
        })

    if progress_callback:
        progress_callback(f"Done! {len(full_text)} chars, {len(segments)} segments")

    return {
        "text": full_text,
        "segments": segments,
    }


def save_transcription(
    text: str,
    output_path: str,
    chunks: Optional[List[str]] = None,
) -> List[str]:
    """
    Save transcription to file(s).

    If chunks is provided (len > 1), saves multiple files:
    output_001.txt, output_002.txt, etc.
    Otherwise saves a single file with the full text.

    Returns list of saved file paths.
    """
    saved = []
    base, ext = os.path.splitext(output_path)
    if not ext:
        ext = ".txt"

    if chunks and len(chunks) > 1:
        for i, chunk in enumerate(chunks, 1):
            chunk_path = f"{base}_{i:03d}{ext}"
            with open(chunk_path, "w", encoding="utf-8") as f:
                f.write(chunk)
            saved.append(chunk_path)
    else:
        with open(f"{base}{ext}", "w", encoding="utf-8") as f:
            f.write(text)
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

    split_group = parser.add_mutually_exclusive_group()
    split_group.add_argument(
        "--split-parts", type=int, default=0,
        help="Split output into N equal parts (e.g., --split-parts 3)",
    )
    split_group.add_argument(
        "--split-chars", type=int, default=0,
        help="Split output every N characters (e.g., --split-chars 2000)",
    )

    args = parser.parse_args()

    cfg = TranscriberConfig(
        model_name=args.model,
        language=args.language,
    )

    if args.output is None:
        base = os.path.splitext(args.audio)[0]
        args.output = f"{base}.txt"

    print(f"Input:    {args.audio}")
    print(f"Model:    {cfg.model_name}")
    print(f"Language: {cfg.language}")
    print()

    def on_status(msg):
        print(f"  {msg}")

    result = transcribe_audio(args.audio, cfg, progress_callback=on_status)
    full_text = result["text"]

    # Split after transcription
    chunks = None
    if args.split_parts > 1:
        chunks = split_text_into_parts(full_text, args.split_parts)
        print(f"\n  Split into {len(chunks)} parts (~{len(chunks[0])} chars each)")
    elif args.split_chars > 0:
        chunks = split_text_by_chars(full_text, args.split_chars)
        print(f"\n  Split into {len(chunks)} chunks (max {args.split_chars} chars each)")

    saved = save_transcription(full_text, args.output, chunks)

    print(f"\nSaved to:")
    for p in saved:
        print(f"  {p}")
    print(f"\nTotal: {len(full_text)} characters, {len(result['segments'])} segments")


if __name__ == "__main__":
    cli_main()
