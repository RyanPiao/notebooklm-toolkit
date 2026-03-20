#!/usr/bin/env python3
"""
NotebookLM Toolkit — Integrated GUI

Tab 1: PDF Cleaner  — Remove watermarks & export 4K PNGs
Tab 2: Audio Transcriber — Transcribe .m4a to text with split option
Tab 3: NotebookLM — Full NotebookLM client (notebooks, sources, generate, chat)
"""

import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext


# ------------------------------------------------------------------ #
#  PDF Cleaner Tab                                                    #
# ------------------------------------------------------------------ #

class PDFCleanerTab:
    def __init__(self, parent):
        self.frame = ttk.Frame(parent, padding=15)
        self.pdf_paths: list = []
        self.cancel_flag = False
        self.running = False
        self._build_ui()

    def _build_ui(self):
        f = self.frame

        # --- Input ---
        ttk.Label(f, text="Input PDFs:").grid(row=0, column=0, sticky="w")
        self.input_var = tk.StringVar()
        ttk.Entry(f, textvariable=self.input_var, width=55).grid(
            row=0, column=1, sticky="ew", padx=(5, 5)
        )
        btn_frame = ttk.Frame(f)
        btn_frame.grid(row=0, column=2, sticky="e")
        ttk.Button(btn_frame, text="Files", command=self._pick_files, width=6).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Folder", command=self._pick_folder, width=6).pack(side="left", padx=2)

        # --- Output ---
        ttk.Label(f, text="Output Folder:").grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.output_var = tk.StringVar(value="cleaned_pngs")
        ttk.Entry(f, textvariable=self.output_var, width=55).grid(
            row=1, column=1, sticky="ew", padx=(5, 5), pady=(8, 0)
        )
        ttk.Button(f, text="Browse", command=self._pick_output, width=8).grid(
            row=1, column=2, sticky="e", pady=(8, 0)
        )

        # --- Settings ---
        settings = ttk.LabelFrame(f, text="Settings", padding=10)
        settings.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(12, 0))

        ttk.Label(settings, text="Resolution (long edge):").grid(row=0, column=0, sticky="w")
        self.resolution_var = tk.IntVar(value=3840)
        res_combo = ttk.Combobox(
            settings, textvariable=self.resolution_var, width=10,
            values=[1920, 2560, 3840, 5120], state="readonly"
        )
        res_combo.grid(row=0, column=1, sticky="w", padx=(5, 20))

        ttk.Label(settings, text="Supersample:").grid(row=0, column=2, sticky="w")
        self.supersample_var = tk.IntVar(value=2)
        ttk.Combobox(
            settings, textvariable=self.supersample_var, width=5,
            values=[1, 2, 3], state="readonly"
        ).grid(row=0, column=3, sticky="w", padx=(5, 20))

        ttk.Label(settings, text="Sharpness:").grid(row=0, column=4, sticky="w")
        self.sharpness_var = tk.DoubleVar(value=1.3)
        ttk.Spinbox(
            settings, textvariable=self.sharpness_var, from_=0.5, to=3.0,
            increment=0.1, width=6
        ).grid(row=0, column=5, sticky="w", padx=(5, 0))

        # --- Info label ---
        self.info_var = tk.StringVar(value="Select PDF files or folder to begin.")
        ttk.Label(f, textvariable=self.info_var, foreground="gray").grid(
            row=3, column=0, columnspan=3, sticky="w", pady=(10, 0)
        )

        # --- Progress ---
        self.progress = ttk.Progressbar(f, mode="determinate", length=500)
        self.progress.grid(row=4, column=0, columnspan=3, sticky="ew", pady=(8, 0))

        self.status_var = tk.StringVar()
        ttk.Label(f, textvariable=self.status_var).grid(
            row=5, column=0, columnspan=3, sticky="w"
        )

        # --- Buttons ---
        btn_row = ttk.Frame(f)
        btn_row.grid(row=6, column=0, columnspan=3, pady=(12, 0))
        self.start_btn = ttk.Button(btn_row, text="Start Processing", command=self._start)
        self.start_btn.pack(side="left", padx=5)
        self.cancel_btn = ttk.Button(btn_row, text="Cancel", command=self._cancel, state="disabled")
        self.cancel_btn.pack(side="left", padx=5)

        f.columnconfigure(1, weight=1)

    def _pick_files(self):
        paths = filedialog.askopenfilenames(
            title="Select PDF files",
            filetypes=[("PDF files", "*.pdf")],
        )
        if paths:
            self.pdf_paths = list(paths)
            self.input_var.set(f"{len(paths)} file(s) selected")
            self._update_info()

    def _pick_folder(self):
        folder = filedialog.askdirectory(title="Select folder with PDFs")
        if folder:
            pdfs = sorted(
                os.path.join(folder, f)
                for f in os.listdir(folder)
                if f.lower().endswith(".pdf")
            )
            self.pdf_paths = pdfs
            self.input_var.set(folder)
            self._update_info()

    def _pick_output(self):
        folder = filedialog.askdirectory(title="Select output folder")
        if folder:
            self.output_var.set(folder)

    def _update_info(self):
        if not self.pdf_paths:
            self.info_var.set("No PDFs selected.")
            return
        from pdf_cleaner_core import get_pdf_page_count
        total = sum(get_pdf_page_count(p) for p in self.pdf_paths)
        self.info_var.set(f"{len(self.pdf_paths)} PDF(s), {total} pages total")

    def _start(self):
        if not self.pdf_paths:
            messagebox.showwarning("No input", "Please select PDF files first.")
            return
        output_dir = self.output_var.get().strip()
        if not output_dir:
            messagebox.showwarning("No output", "Please set an output folder.")
            return

        self.running = True
        self.cancel_flag = False
        self.start_btn.config(state="disabled")
        self.cancel_btn.config(state="normal")
        self.progress["value"] = 0

        thread = threading.Thread(target=self._run_batch, args=(output_dir,), daemon=True)
        thread.start()

    def _cancel(self):
        self.cancel_flag = True
        self.status_var.set("Cancelling...")

    def _run_batch(self, output_dir):
        from pdf_cleaner_core import CleanerConfig, run_batch

        cfg = CleanerConfig(
            target_long_edge=self.resolution_var.get(),
            supersample=self.supersample_var.get(),
            sharpness_factor=self.sharpness_var.get(),
        )

        def on_progress(completed, total, status):
            self.frame.after(0, self._update_progress, completed, total, status)

        def check_cancel():
            return self.cancel_flag

        success, errors = run_batch(
            self.pdf_paths, output_dir, cfg,
            progress_callback=on_progress,
            cancel_check=check_cancel,
        )

        self.frame.after(0, self._on_done, success, errors, output_dir)

    def _update_progress(self, completed, total, status):
        if total > 0:
            self.progress["value"] = completed / total * 100
        self.status_var.set(status)

    def _on_done(self, success, errors, output_dir):
        self.running = False
        self.start_btn.config(state="normal")
        self.cancel_btn.config(state="disabled")
        if self.cancel_flag:
            self.status_var.set(f"Cancelled. {success} pages completed before cancel.")
        else:
            self.status_var.set(f"Done! {success} pages exported, {errors} errors.")
            self.progress["value"] = 100
        messagebox.showinfo(
            "Complete",
            f"{success} pages exported to:\n{os.path.abspath(output_dir)}"
            + (f"\n{errors} errors." if errors else ""),
        )


# ------------------------------------------------------------------ #
#  Audio Transcriber Tab                                              #
# ------------------------------------------------------------------ #

class AudioTranscriberTab:
    def __init__(self, parent):
        self.frame = ttk.Frame(parent, padding=15)
        self.running = False
        self.full_text = ""       # raw transcription text
        self.chunks: list = []    # current split chunks
        self.current_chunk = 0
        self._build_ui()

    def _build_ui(self):
        f = self.frame

        # --- Input ---
        ttk.Label(f, text="Audio File (.m4a):").grid(row=0, column=0, sticky="w")
        self.input_var = tk.StringVar()
        ttk.Entry(f, textvariable=self.input_var, width=55).grid(
            row=0, column=1, sticky="ew", padx=(5, 5)
        )
        ttk.Button(f, text="Browse", command=self._pick_file, width=8).grid(
            row=0, column=2, sticky="e"
        )

        # --- Transcription settings (before transcribe) ---
        settings = ttk.LabelFrame(f, text="Transcription Settings", padding=10)
        settings.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(12, 0))

        ttk.Label(settings, text="Model:").grid(row=0, column=0, sticky="w")
        self.model_var = tk.StringVar(value="small")
        ttk.Combobox(
            settings, textvariable=self.model_var, width=10,
            values=["tiny", "base", "small", "medium", "large"], state="readonly"
        ).grid(row=0, column=1, sticky="w", padx=(5, 20))

        ttk.Label(settings, text="Language:").grid(row=0, column=2, sticky="w")
        self.language_var = tk.StringVar(value="en")
        ttk.Entry(settings, textvariable=self.language_var, width=6).grid(
            row=0, column=3, sticky="w", padx=(5, 0)
        )

        # --- Status & progress ---
        self.status_var = tk.StringVar(value="Select an .m4a file to begin.")
        ttk.Label(f, textvariable=self.status_var, foreground="gray").grid(
            row=2, column=0, columnspan=3, sticky="w", pady=(10, 0)
        )

        self.progress = ttk.Progressbar(f, mode="indeterminate", length=500)
        self.progress.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(8, 0))

        # --- Transcribe button ---
        self.transcribe_btn = ttk.Button(
            f, text="Transcribe", command=self._start_transcribe
        )
        self.transcribe_btn.grid(row=4, column=0, columnspan=3, pady=(10, 0))

        # --- Split controls (shown after transcription) ---
        self.split_frame = ttk.LabelFrame(f, text="Split Text", padding=10)
        self.split_frame.grid(row=5, column=0, columnspan=3, sticky="ew", pady=(12, 0))

        ttk.Label(self.split_frame, text="Split into").grid(row=0, column=0, sticky="w")
        self.split_parts_var = tk.IntVar(value=1)
        self.split_spinbox = ttk.Spinbox(
            self.split_frame, textvariable=self.split_parts_var,
            from_=1, to=50, increment=1, width=5
        )
        self.split_spinbox.grid(row=0, column=1, sticky="w", padx=(5, 5))
        ttk.Label(self.split_frame, text="equal parts").grid(row=0, column=2, sticky="w")

        ttk.Label(self.split_frame, text="Overlap:").grid(row=0, column=3, sticky="w", padx=(15, 0))
        self.overlap_var = tk.IntVar(value=500)
        self.overlap_spinbox = ttk.Spinbox(
            self.split_frame, textvariable=self.overlap_var,
            from_=0, to=5000, increment=100, width=6
        )
        self.overlap_spinbox.grid(row=0, column=4, sticky="w", padx=(5, 5))
        ttk.Label(self.split_frame, text="chars", foreground="gray").grid(row=0, column=5, sticky="w")

        self.apply_split_btn = ttk.Button(
            self.split_frame, text="Apply Split", command=self._apply_split
        )
        self.apply_split_btn.grid(row=0, column=6, sticky="w", padx=(15, 10))

        self.chars_info_var = tk.StringVar()
        ttk.Label(
            self.split_frame, textvariable=self.chars_info_var, foreground="gray"
        ).grid(row=1, column=0, columnspan=7, sticky="w", pady=(5, 0))

        # Initially disable split controls
        self._set_split_enabled(False)

        # --- Chunk navigation & action buttons ---
        nav_frame = ttk.Frame(f)
        nav_frame.grid(row=6, column=0, columnspan=3, sticky="ew", pady=(8, 0))

        self.chunk_label = tk.StringVar()
        ttk.Label(nav_frame, textvariable=self.chunk_label).pack(side="left")
        self.prev_btn = ttk.Button(
            nav_frame, text="< Prev", command=self._prev_chunk, state="disabled"
        )
        self.prev_btn.pack(side="left", padx=5)
        self.next_btn = ttk.Button(
            nav_frame, text="Next >", command=self._next_chunk, state="disabled"
        )
        self.next_btn.pack(side="left", padx=5)
        self.copy_chunk_btn = ttk.Button(
            nav_frame, text="Copy Chunk", command=self._copy_chunk, state="disabled"
        )
        self.copy_chunk_btn.pack(side="left", padx=5)

        # Spacer
        ttk.Frame(nav_frame).pack(side="left", expand=True)

        self.copy_btn = ttk.Button(
            nav_frame, text="Copy All", command=self._copy_all, state="disabled"
        )
        self.copy_btn.pack(side="right", padx=5)
        self.save_btn = ttk.Button(
            nav_frame, text="Save", command=self._save_text, state="disabled"
        )
        self.save_btn.pack(side="right", padx=5)

        # --- Text output ---
        self.text_area = scrolledtext.ScrolledText(f, wrap="word", height=16, width=70)
        self.text_area.grid(row=7, column=0, columnspan=3, sticky="nsew", pady=(4, 0))

        f.columnconfigure(1, weight=1)
        f.rowconfigure(7, weight=1)

    def _set_split_enabled(self, enabled):
        state = "normal" if enabled else "disabled"
        self.split_spinbox.config(state=state)
        self.overlap_spinbox.config(state=state)
        self.apply_split_btn.config(state=state)

    def _set_nav_enabled(self, has_chunks):
        if has_chunks:
            self.prev_btn.config(state="normal")
            self.next_btn.config(state="normal")
            self.copy_chunk_btn.config(state="normal")
        else:
            self.prev_btn.config(state="disabled")
            self.next_btn.config(state="disabled")
            self.copy_chunk_btn.config(state="disabled")

    def _pick_file(self):
        path = filedialog.askopenfilename(
            title="Select .m4a audio file",
            filetypes=[("M4A Audio", "*.m4a")],
        )
        if path:
            self.input_var.set(path)
            size_mb = os.path.getsize(path) / (1024 * 1024)
            self.status_var.set(f"Selected: {os.path.basename(path)} ({size_mb:.1f} MB)")

    def _start_transcribe(self):
        audio_path = self.input_var.get().strip()
        if not audio_path or not os.path.isfile(audio_path):
            messagebox.showwarning("No file", "Please select a valid .m4a file.")
            return

        self.running = True
        self.transcribe_btn.config(state="disabled")
        self.save_btn.config(state="disabled")
        self.copy_btn.config(state="disabled")
        self._set_split_enabled(False)
        self._set_nav_enabled(False)
        self.progress.start(10)
        self.text_area.delete("1.0", "end")

        thread = threading.Thread(target=self._run_transcribe, args=(audio_path,), daemon=True)
        thread.start()

    def _run_transcribe(self, audio_path):
        from audio_transcriber import TranscriberConfig, transcribe_audio

        cfg = TranscriberConfig(
            model_name=self.model_var.get(),
            language=self.language_var.get(),
        )

        def on_status(msg):
            self.frame.after(0, lambda: self.status_var.set(msg))

        try:
            result = transcribe_audio(audio_path, cfg, progress_callback=on_status)
            self.frame.after(0, self._on_transcribe_done, result, None)
        except Exception as e:
            self.frame.after(0, self._on_transcribe_done, None, str(e))

    def _on_transcribe_done(self, result, error):
        self.running = False
        self.progress.stop()
        self.transcribe_btn.config(state="normal")

        if error:
            self.status_var.set(f"Error: {error}")
            messagebox.showerror("Transcription Error", error)
            return

        self.full_text = result["text"]
        self.chunks = [self.full_text]
        self.current_chunk = 0

        total_chars = len(self.full_text)
        segs = len(result["segments"])
        self.status_var.set(f"Done! {total_chars} chars, {segs} segments. Use Split to divide the text.")
        self.chars_info_var.set(f"Total: {total_chars} chars")

        # Enable post-transcription controls
        self.save_btn.config(state="normal")
        self.copy_btn.config(state="normal")
        self._set_split_enabled(True)
        self.split_parts_var.set(1)

        self._show_chunk(0)

    def _apply_split(self):
        """Re-split the full text into N equal parts with overlap."""
        if not self.full_text:
            return

        from audio_transcriber import split_text_into_parts

        num_parts = self.split_parts_var.get()
        if num_parts < 1:
            num_parts = 1
            self.split_parts_var.set(1)

        overlap = self.overlap_var.get()
        if overlap < 0:
            overlap = 0
            self.overlap_var.set(0)

        self.chunks = split_text_into_parts(self.full_text, num_parts, overlap)
        self.current_chunk = 0

        total_chars = len(self.full_text)
        overlap_info = f", {overlap}-char overlap" if overlap > 0 and num_parts > 1 else ""
        self.chars_info_var.set(
            f"Total: {total_chars} chars | {len(self.chunks)} parts{overlap_info}"
        )
        self.status_var.set(f"Split into {len(self.chunks)} parts")

        self._set_nav_enabled(len(self.chunks) > 1)
        self._show_chunk(0)

    def _show_chunk(self, idx):
        if not self.chunks:
            return
        idx = max(0, min(idx, len(self.chunks) - 1))
        self.current_chunk = idx

        self.text_area.delete("1.0", "end")
        self.text_area.insert("1.0", self.chunks[idx])

        if len(self.chunks) > 1:
            self.chunk_label.set(
                f"Part {idx + 1}/{len(self.chunks)}  ({len(self.chunks[idx])} chars)"
            )
        else:
            self.chunk_label.set(f"{len(self.chunks[0])} chars")

    def _prev_chunk(self):
        self._show_chunk(self.current_chunk - 1)

    def _next_chunk(self):
        self._show_chunk(self.current_chunk + 1)

    def _copy_all(self):
        if self.full_text:
            self.frame.clipboard_clear()
            self.frame.clipboard_append(self.full_text)
            self.status_var.set("Full text copied to clipboard.")

    def _copy_chunk(self):
        if self.chunks:
            chunk = self.chunks[self.current_chunk]
            self.frame.clipboard_clear()
            self.frame.clipboard_append(chunk)
            self.status_var.set(f"Part {self.current_chunk + 1} copied to clipboard.")

    def _save_text(self):
        if not self.full_text:
            return

        from audio_transcriber import save_transcription

        path = filedialog.asksaveasfilename(
            title="Save transcription",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt")],
        )
        if not path:
            return

        chunks_to_save = self.chunks if len(self.chunks) > 1 else None
        saved = save_transcription(self.full_text, path, chunks_to_save)
        self.status_var.set(f"Saved {len(saved)} file(s)")
        messagebox.showinfo("Saved", "Saved to:\n" + "\n".join(saved))


# ------------------------------------------------------------------ #
#  Main Application                                                   #
# ------------------------------------------------------------------ #

class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("NotebookLM Toolkit")
        self.root.geometry("950x720")
        self.root.minsize(800, 600)

        # Style
        style = ttk.Style()
        try:
            style.theme_use("aqua")  # macOS native
        except tk.TclError:
            try:
                style.theme_use("clam")  # fallback
            except tk.TclError:
                pass

        # Tabs
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)

        self.pdf_tab = PDFCleanerTab(notebook)
        notebook.add(self.pdf_tab.frame, text="  PDF Cleaner  ")

        self.audio_tab = AudioTranscriberTab(notebook)
        notebook.add(self.audio_tab.frame, text="  Audio Transcriber  ")

        # NotebookLM tab (optional — only if notebooklm-py is installed)
        try:
            from notebooklm_tab import NotebookLMTab
            self.nlm_tab = NotebookLMTab(notebook)
            notebook.add(self.nlm_tab.frame, text="  NotebookLM  ")
        except ImportError:
            pass  # notebooklm-py not installed, skip tab

    def run(self):
        self.root.mainloop()


def main():
    app = App()
    app.run()


if __name__ == "__main__":
    main()
