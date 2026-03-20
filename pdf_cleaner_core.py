#!/usr/bin/env python3
"""
NotebookLM PDF Cleaner — Core Engine

Removes NotebookLM watermarks from PDFs using OpenCV inpainting,
then exports each page as a high-quality 4K PNG.
"""

import fitz  # PyMuPDF
import cv2
import numpy as np
import os
import io
import concurrent.futures
import multiprocessing as mp
from dataclasses import dataclass
from typing import Optional, List, Callable, Tuple
from PIL import Image, ImageEnhance

# Allow large images
Image.MAX_IMAGE_PIXELS = None


# ------------------------------------------------------------------ #
#  Configuration                                                      #
# ------------------------------------------------------------------ #

@dataclass
class CleanerConfig:
    """All settings for watermark removal and PNG rendering."""

    # --- Watermark detection ---
    search_margin_x: int = 300
    search_margin_y: int = 65
    watermark_padding: int = 8
    pixel_threshold: int = 30
    inpaint_radius: int = 5
    min_watermark_components: int = 1
    min_watermark_area: int = 800
    min_component_area: int = 200
    wm_dpi_scale: float = 3.0

    # --- PNG rendering ---
    target_long_edge: int = 3840
    supersample: int = 2
    sharpness_factor: float = 1.3
    png_compress_level: int = 1

    # --- Parallelism ---
    max_workers: int = 0


# ------------------------------------------------------------------ #
#  Watermark detection & removal                                      #
# ------------------------------------------------------------------ #

WATERMARK_TEXT = "NotebookLM"


def _build_watermark_mask(
    roi_bgr: np.ndarray, cfg: CleanerConfig
) -> Optional[np.ndarray]:
    """Build a pixel-precise mask covering only the watermark pixels."""
    h, w = roi_bgr.shape[:2]
    if h < 5 or w < 5:
        return None

    ksize = max(11, min(31, (min(h, w) // 6) | 1))
    background = cv2.medianBlur(roi_bgr, ksize)
    diff_gray = cv2.cvtColor(
        cv2.absdiff(roi_bgr, background), cv2.COLOR_BGR2GRAY
    )
    _, binary = cv2.threshold(
        diff_gray, cfg.pixel_threshold, 255, cv2.THRESH_BINARY
    )

    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(
        binary, connectivity=8
    )

    wm_labels: List[int] = []
    for i in range(1, num_labels):
        cx, cy, cw, ch, area = stats[i]
        if area < cfg.min_component_area:
            continue
        if cx + cw / 2 < w * 0.5:
            continue
        if cy + ch / 2 < h * 0.5:
            continue
        if cw > w * 0.7 or ch > h * 0.8:
            continue
        wm_labels.append(i)

    if len(wm_labels) < cfg.min_watermark_components:
        return None

    total_area = sum(int(stats[i][4]) for i in wm_labels)
    if total_area < cfg.min_watermark_area:
        return None

    mask = np.zeros((h, w), dtype=np.uint8)
    for lid in wm_labels:
        mask[labels == lid] = 255

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    mask = cv2.dilate(mask, kernel, iterations=3)
    return mask if cv2.countNonZero(mask) > 0 else None


def _pixmap_to_bgr(pix: fitz.Pixmap) -> Optional[np.ndarray]:
    """Convert PyMuPDF Pixmap to BGR numpy array."""
    data = np.frombuffer(pix.samples, dtype=np.uint8)
    if pix.n == 4:
        return cv2.cvtColor(data.reshape(pix.h, pix.w, 4), cv2.COLOR_RGBA2BGR)
    if pix.n == 3:
        return cv2.cvtColor(data.reshape(pix.h, pix.w, 3), cv2.COLOR_RGB2BGR)
    return None


def _find_watermark_rect_text(
    page: fitz.Page, cfg: CleanerConfig
) -> Optional[fitz.Rect]:
    """Locate watermark via PDF text search."""
    w, h = page.rect.width, page.rect.height
    instances = page.search_for(WATERMARK_TEXT)
    if not instances:
        return None

    best: Optional[fitz.Rect] = None
    best_score = float("inf")

    for rect in instances:
        cy = (rect.y0 + rect.y1) / 2
        cx = (rect.x0 + rect.x1) / 2
        if cy < h * 0.80 or rect.width > 250 or rect.height > 40:
            continue
        dist = abs(w - cx) + abs(h - cy)
        if dist < best_score:
            best_score = dist
            best = rect

    if best is None:
        return None

    wm_rect = fitz.Rect(best)
    icon_zone = fitz.Rect(best.x0 - 80, best.y0 - 15, best.x0 + 5, best.y1 + 15)
    try:
        for d in page.get_drawings():
            if d["rect"].intersects(icon_zone):
                wm_rect = wm_rect | d["rect"]
    except Exception:
        pass
    try:
        for img_info in page.get_images(full=True):
            for ir in page.get_image_rects(img_info[0]):
                if ir.intersects(icon_zone):
                    wm_rect = wm_rect | ir
    except Exception:
        pass

    wm_rect.x0 = min(wm_rect.x0, best.x0 - 45)
    pad = cfg.watermark_padding
    return fitz.Rect(
        max(0, wm_rect.x0 - pad),
        max(0, wm_rect.y0 - pad),
        min(w, wm_rect.x1 + pad),
        min(h, wm_rect.y1 + pad),
    )


def _patch_pdf_rect(
    page: fitz.Page, rect: fitz.Rect, cfg: CleanerConfig, precision: bool = True
) -> bool:
    """Rasterize rect, clean watermark via inpainting, paste back."""
    mat = fitz.Matrix(cfg.wm_dpi_scale, cfg.wm_dpi_scale)
    pix = page.get_pixmap(clip=rect, matrix=mat)
    roi_bgr = _pixmap_to_bgr(pix)
    if roi_bgr is None:
        return False

    if precision:
        mask = _build_watermark_mask(roi_bgr, cfg)
        if mask is None:
            return False
        cleaned = cv2.inpaint(roi_bgr, mask, cfg.inpaint_radius, cv2.INPAINT_TELEA)
    else:
        h, w = roi_bgr.shape[:2]
        if h < 5 or w < 5:
            return False
        ksize = max(11, min(31, (min(h, w) // 6) | 1))
        background = cv2.medianBlur(roi_bgr, ksize)
        diff_gray = cv2.cvtColor(
            cv2.absdiff(roi_bgr, background), cv2.COLOR_BGR2GRAY
        )
        _, mask = cv2.threshold(
            diff_gray, cfg.pixel_threshold, 255, cv2.THRESH_BINARY
        )
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        mask = cv2.dilate(mask, kernel, iterations=3)
        if cv2.countNonZero(mask) == 0:
            return False
        cleaned = cv2.inpaint(roi_bgr, mask, cfg.inpaint_radius, cv2.INPAINT_TELEA)

    cleaned_rgb = cv2.cvtColor(cleaned, cv2.COLOR_BGR2RGB)
    buf = io.BytesIO()
    Image.fromarray(cleaned_rgb).save(buf, format="PNG")
    page.insert_image(rect, stream=buf.getvalue())
    return True


def remove_watermark_from_page(page: fitz.Page, cfg: CleanerConfig) -> bool:
    """Remove NotebookLM watermark from a single PDF page (in-memory)."""
    w, h = page.rect.width, page.rect.height

    # Strategy 1: text-based
    wm_rect = _find_watermark_rect_text(page, cfg)
    if wm_rect is not None:
        if _patch_pdf_rect(page, wm_rect, cfg, precision=False):
            return True

    # Strategy 2: pixel-based corner detection
    corner = fitz.Rect(
        max(0, w - cfg.search_margin_x),
        max(0, h - cfg.search_margin_y),
        w, h,
    )
    return _patch_pdf_rect(page, corner, cfg, precision=True)


# ------------------------------------------------------------------ #
#  High-quality PNG rendering                                         #
# ------------------------------------------------------------------ #

def render_page_to_png(
    page: fitz.Page, output_path: str, cfg: CleanerConfig
) -> None:
    """Render a cleaned PDF page to a 4K PNG with supersample + Lanczos."""
    pw, ph = page.rect.width, page.rect.height
    if pw >= ph:
        target_width = cfg.target_long_edge
        target_height = int(cfg.target_long_edge * ph / pw)
    else:
        target_height = cfg.target_long_edge
        target_width = int(cfg.target_long_edge * pw / ph)

    target_dpi = target_width / (pw / 72.0)
    render_dpi = target_dpi * cfg.supersample
    zoom = render_dpi / 72.0

    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat)

    img_data = pix.tobytes("png")
    pil_image = Image.open(io.BytesIO(img_data))

    if cfg.supersample > 1:
        pil_image = pil_image.resize(
            (target_width, target_height), resample=Image.LANCZOS
        )

    if cfg.sharpness_factor != 1.0:
        enhancer = ImageEnhance.Sharpness(pil_image)
        pil_image = enhancer.enhance(cfg.sharpness_factor)

    pil_image.save(output_path, format="PNG", compress_level=cfg.png_compress_level)
    pil_image.close()


# ------------------------------------------------------------------ #
#  Multiprocessing worker                                             #
# ------------------------------------------------------------------ #

def _process_single_page(task: Tuple) -> str:
    """Worker function for ProcessPoolExecutor."""
    pdf_path, page_num, output_path, cfg = task
    doc = None
    try:
        doc = fitz.open(pdf_path)
        page = doc.load_page(page_num)
        remove_watermark_from_page(page, cfg)
        render_page_to_png(page, output_path, cfg)
        return f"OK|{pdf_path}|{page_num}"
    except Exception as e:
        return f"ERR|{pdf_path}|{page_num}|{e}"
    finally:
        if doc:
            doc.close()


# ------------------------------------------------------------------ #
#  Batch processing                                                   #
# ------------------------------------------------------------------ #

def get_pdf_page_count(pdf_path: str) -> int:
    """Return page count for a PDF."""
    doc = fitz.open(pdf_path)
    count = doc.page_count
    doc.close()
    return count


def build_task_list(
    pdf_paths: List[str], output_dir: str, cfg: CleanerConfig
) -> List[Tuple]:
    """Build list of (pdf_path, page_num, output_png_path, cfg) tuples."""
    tasks = []
    for pdf_path in pdf_paths:
        pdf_name = os.path.splitext(os.path.basename(pdf_path))[0]
        pdf_out_dir = os.path.join(output_dir, pdf_name)
        os.makedirs(pdf_out_dir, exist_ok=True)

        doc = fitz.open(pdf_path)
        page_count = doc.page_count
        doc.close()

        for i in range(page_count):
            out_name = f"page_{i + 1:03d}.png"
            out_path = os.path.join(pdf_out_dir, out_name)
            tasks.append((pdf_path, i, out_path, cfg))

    return tasks


def run_batch(
    pdf_paths: List[str],
    output_dir: str,
    cfg: CleanerConfig,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
    cancel_check: Optional[Callable[[], bool]] = None,
) -> Tuple[int, int]:
    """
    Process all PDFs: remove watermarks and export pages as 4K PNGs.

    Returns:
        (success_count, error_count)
    """
    os.makedirs(output_dir, exist_ok=True)
    tasks = build_task_list(pdf_paths, output_dir, cfg)
    total = len(tasks)

    if total == 0:
        return (0, 0)

    workers = cfg.max_workers if cfg.max_workers > 0 else min(os.cpu_count() or 2, 4)
    ctx = mp.get_context("spawn")

    success = 0
    errors = 0

    with concurrent.futures.ProcessPoolExecutor(
        max_workers=workers, mp_context=ctx
    ) as executor:
        futures = {executor.submit(_process_single_page, t): t for t in tasks}

        for future in concurrent.futures.as_completed(futures):
            if cancel_check and cancel_check():
                executor.shutdown(wait=False, cancel_futures=True)
                break

            result = future.result()
            if result.startswith("OK"):
                success += 1
            else:
                errors += 1

            if progress_callback:
                parts = result.split("|")
                pdf_name = os.path.basename(parts[1]) if len(parts) > 1 else ""
                page = int(parts[2]) + 1 if len(parts) > 2 else 0
                status = f"{pdf_name} page {page}"
                if result.startswith("ERR") and len(parts) > 3:
                    status += f" - ERROR: {parts[3]}"
                progress_callback(success + errors, total, status)

    return (success, errors)


# ------------------------------------------------------------------ #
#  CLI                                                                #
# ------------------------------------------------------------------ #

def cli_main():
    """Command-line interface for the PDF cleaner."""
    import argparse

    parser = argparse.ArgumentParser(
        description="NotebookLM PDF Cleaner - Remove watermarks & export 4K PNGs"
    )
    parser.add_argument("path", help="PDF file or directory containing PDFs")
    parser.add_argument(
        "-o", "--output", default="cleaned_pngs",
        help="Output directory (default: ./cleaned_pngs)",
    )
    parser.add_argument(
        "--resolution", type=int, default=3840,
        help="Target long-edge resolution in pixels (default: 3840 for 4K)",
    )
    parser.add_argument(
        "--supersample", type=int, default=2,
        help="Supersample factor (default: 2)",
    )
    parser.add_argument(
        "--sharpness", type=float, default=1.3,
        help="Sharpness enhancement factor (default: 1.3, 1.0 = off)",
    )
    parser.add_argument(
        "--workers", type=int, default=0,
        help="Max parallel workers (default: auto)",
    )
    parser.add_argument(
        "--margin-x", type=int, default=None,
        help="Watermark search margin from right edge (default: 300)",
    )
    parser.add_argument(
        "--margin-y", type=int, default=None,
        help="Watermark search margin from bottom edge (default: 65)",
    )

    args = parser.parse_args()

    cfg = CleanerConfig(
        target_long_edge=args.resolution,
        supersample=args.supersample,
        sharpness_factor=args.sharpness,
        max_workers=args.workers,
    )
    if args.margin_x is not None:
        cfg.search_margin_x = args.margin_x
    if args.margin_y is not None:
        cfg.search_margin_y = args.margin_y

    input_path = args.path
    if os.path.isdir(input_path):
        pdf_paths = sorted(
            os.path.join(input_path, f)
            for f in os.listdir(input_path)
            if f.lower().endswith(".pdf")
        )
    elif os.path.isfile(input_path) and input_path.lower().endswith(".pdf"):
        pdf_paths = [input_path]
    else:
        print(f"Error: '{input_path}' is not a valid PDF file or directory.")
        return

    if not pdf_paths:
        print("No PDF files found.")
        return

    total_pages = sum(get_pdf_page_count(p) for p in pdf_paths)
    print(f"Found {len(pdf_paths)} PDF(s), {total_pages} pages total.")
    print(f"Output: {os.path.abspath(args.output)}")
    print(f"Resolution: {cfg.target_long_edge}px, {cfg.supersample}x supersample")
    print()

    def on_progress(completed, total, status):
        pct = int(completed / total * 100) if total else 0
        print(f"  [{completed}/{total}] {pct}% - {status}")

    success, errors = run_batch(
        pdf_paths, args.output, cfg, progress_callback=on_progress
    )
    print(f"\nDone! {success} pages exported, {errors} errors.")
    print(f"Output: {os.path.abspath(args.output)}")


if __name__ == "__main__":
    cli_main()
