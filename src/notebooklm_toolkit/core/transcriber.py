#!/usr/bin/env python3
"""
Audio Transcriber — Core Engine

Transcribes audio files to text using faster-whisper (local),
with option to split output into equal parts after transcription.
"""

import os
from dataclasses import dataclass
from typing import Optional, Callable, List


AVAILABLE_MODELS = ["tiny", "base", "small", "medium", "large-v3"]


@dataclass
class TranscriberConfig:
    model_name: str = "small"
    language: str = "en"


def _find_word_boundary(text, pos):
    if pos >= len(text):
        return len(text)
    if pos <= 0:
        return 0
    fwd = text.find(" ", pos)
    if fwd != -1 and fwd - pos < 200:
        return fwd
    bwd = text.rfind(" ", 0, pos)
    if bwd != -1:
        return bwd
    return pos


def split_text_by_chars(text, max_chars):
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


def split_text_into_parts(text, num_parts, overlap_chars=500):
    text = text.strip()
    if num_parts <= 1 or not text:
        return [text] if text else [""]
    total = len(text)
    split_points = []
    for i in range(1, num_parts):
        ideal_pos = int(total * i / num_parts)
        actual_pos = _find_word_boundary(text, ideal_pos)
        split_points.append(actual_pos)
    boundaries = [0] + split_points + [total]
    segments = []
    for i in range(len(boundaries) - 1):
        seg = text[boundaries[i]:boundaries[i + 1]].strip()
        segments.append(seg)
    if overlap_chars > 0 and len(segments) > 1:
        chunks = [segments[0]]
        for i in range(1, len(segments)):
            prev_text = segments[i - 1]
            if len(prev_text) <= overlap_chars:
                overlap = prev_text
            else:
                overlap_start = len(prev_text) - overlap_chars
                bwd = prev_text.find(" ", overlap_start)
                if bwd != -1 and bwd < len(prev_text):
                    overlap = prev_text[bwd:].strip()
                else:
                    overlap = prev_text[overlap_start:].strip()
            chunks.append(f"[...continued]\n{overlap}\n\n{segments[i]}")
        return chunks
    return segments


def transcribe_audio(audio_path, cfg, progress_callback=None):
    """
    Transcribe an audio file using faster-whisper (local).

    Returns dict with keys: "text", "segments"
    """
    if not os.path.isfile(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    from faster_whisper import WhisperModel

    # Detect best device
    device = "cpu"
    compute_type = "int8"
    try:
        import torch
        if torch.cuda.is_available():
            device = "cuda"
            compute_type = "float16"
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            device = "cpu"  # faster-whisper uses CTranslate2 which doesn't support MPS directly
            compute_type = "int8"
    except ImportError:
        pass

    device_label = "GPU (CUDA)" if device == "cuda" else "CPU"
    if progress_callback:
        progress_callback(f"Loading model '{cfg.model_name}' on {device_label}...")

    model = WhisperModel(cfg.model_name, device=device, compute_type=compute_type)

    if progress_callback:
        progress_callback(f"Transcribing on {device_label} (this may take several minutes)...")

    segments_iter, info = model.transcribe(
        audio_path,
        language=cfg.language,
        beam_size=5,
    )

    segments = []
    text_parts = []
    for seg in segments_iter:
        segments.append({
            "start": seg.start,
            "end": seg.end,
            "text": seg.text.strip(),
        })
        text_parts.append(seg.text.strip())

    full_text = " ".join(text_parts)

    if progress_callback:
        progress_callback(f"Done! {len(full_text)} chars, {len(segments)} segments")

    return {"text": full_text, "segments": segments}


def save_transcription(text, output_path, chunks=None):
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
