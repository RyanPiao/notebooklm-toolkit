#!/usr/bin/env python3
"""
NotebookLM GUI Tab — Full integration with notebooklm-py.

Provides notebook management, source management, artifact generation
with all parameters, chat, and download with auto-processing.
"""

import os
import tempfile
import threading
import time
import tkinter as tk
import tkinter.simpledialog
from tkinter import ttk, filedialog, messagebox, scrolledtext
import json
from pathlib import Path

# Import enums from notebooklm-py
try:
    from notebooklm import (
        AudioFormat, AudioLength,
        VideoFormat, VideoStyle,
        ReportFormat,
        QuizQuantity, QuizDifficulty,
        InfographicOrientation, InfographicDetail, InfographicStyle,
        SlideDeckFormat, SlideDeckLength,
    )
    _HAS_ENUMS = True
except ImportError:
    _HAS_ENUMS = False


# ------------------------------------------------------------------ #
#  Enum display mappings                                              #
# ------------------------------------------------------------------ #

if _HAS_ENUMS:
    AUDIO_FORMATS = {
        "Deep Dive": AudioFormat.DEEP_DIVE, "Brief": AudioFormat.BRIEF,
        "Critique": AudioFormat.CRITIQUE, "Debate": AudioFormat.DEBATE,
    }
    AUDIO_LENGTHS = {
        "Short": AudioLength.SHORT, "Default": AudioLength.DEFAULT, "Long": AudioLength.LONG,
    }
    VIDEO_FORMATS = {
        "Explainer": VideoFormat.EXPLAINER, "Brief": VideoFormat.BRIEF, "Cinematic": VideoFormat.CINEMATIC,
    }
    VIDEO_STYLES = {
        "Auto Select": VideoStyle.AUTO_SELECT, "Custom": VideoStyle.CUSTOM,
        "Classic": VideoStyle.CLASSIC, "Whiteboard": VideoStyle.WHITEBOARD,
        "Kawaii": VideoStyle.KAWAII, "Anime": VideoStyle.ANIME,
        "Watercolor": VideoStyle.WATERCOLOR, "Retro Print": VideoStyle.RETRO_PRINT,
        "Heritage": VideoStyle.HERITAGE, "Paper Craft": VideoStyle.PAPER_CRAFT,
    }
    REPORT_FORMATS = {
        "Briefing Doc": ReportFormat.BRIEFING_DOC, "Study Guide": ReportFormat.STUDY_GUIDE,
        "Blog Post": ReportFormat.BLOG_POST, "Custom": ReportFormat.CUSTOM,
    }
    QUIZ_QUANTITIES = {"Fewer": QuizQuantity.FEWER, "Standard": QuizQuantity.STANDARD}
    QUIZ_DIFFICULTIES = {"Easy": QuizDifficulty.EASY, "Medium": QuizDifficulty.MEDIUM, "Hard": QuizDifficulty.HARD}
    INFOGRAPHIC_ORIENTATIONS = {
        "Landscape": InfographicOrientation.LANDSCAPE, "Portrait": InfographicOrientation.PORTRAIT,
        "Square": InfographicOrientation.SQUARE,
    }
    INFOGRAPHIC_DETAILS = {
        "Concise": InfographicDetail.CONCISE, "Standard": InfographicDetail.STANDARD,
        "Detailed": InfographicDetail.DETAILED,
    }
    INFOGRAPHIC_STYLES = {
        "Auto Select": InfographicStyle.AUTO_SELECT, "Sketch Note": InfographicStyle.SKETCH_NOTE,
        "Professional": InfographicStyle.PROFESSIONAL, "Bento Grid": InfographicStyle.BENTO_GRID,
        "Editorial": InfographicStyle.EDITORIAL, "Instructional": InfographicStyle.INSTRUCTIONAL,
        "Bricks": InfographicStyle.BRICKS, "Clay": InfographicStyle.CLAY,
        "Anime": InfographicStyle.ANIME, "Kawaii": InfographicStyle.KAWAII,
        "Scientific": InfographicStyle.SCIENTIFIC,
    }
    SLIDE_FORMATS = {"Detailed Deck": SlideDeckFormat.DETAILED_DECK, "Presenter Slides": SlideDeckFormat.PRESENTER_SLIDES}
    SLIDE_LENGTHS = {"Default": SlideDeckLength.DEFAULT, "Short": SlideDeckLength.SHORT}
else:
    AUDIO_FORMATS = {"Deep Dive": 1, "Brief": 2, "Critique": 3, "Debate": 4}
    AUDIO_LENGTHS = {"Short": 1, "Default": 2, "Long": 3}
    VIDEO_FORMATS = {"Explainer": 1, "Brief": 2, "Cinematic": 3}
    VIDEO_STYLES = {"Auto Select": 1, "Custom": 2, "Classic": 3, "Whiteboard": 4,
                    "Kawaii": 5, "Anime": 6, "Watercolor": 7, "Retro Print": 8,
                    "Heritage": 9, "Paper Craft": 10}
    REPORT_FORMATS = {"Briefing Doc": "briefing_doc", "Study Guide": "study_guide",
                      "Blog Post": "blog_post", "Custom": "custom"}
    QUIZ_QUANTITIES = {"Fewer": 1, "Standard": 2}
    QUIZ_DIFFICULTIES = {"Easy": 1, "Medium": 2, "Hard": 3}
    INFOGRAPHIC_ORIENTATIONS = {"Landscape": 1, "Portrait": 2, "Square": 3}
    INFOGRAPHIC_DETAILS = {"Concise": 1, "Standard": 2, "Detailed": 3}
    INFOGRAPHIC_STYLES = {"Auto Select": 1, "Sketch Note": 2, "Professional": 3,
                          "Bento Grid": 4, "Editorial": 5, "Instructional": 6,
                          "Bricks": 7, "Clay": 8, "Anime": 9, "Kawaii": 10, "Scientific": 11}
    SLIDE_FORMATS = {"Detailed Deck": 1, "Presenter Slides": 2}
    SLIDE_LENGTHS = {"Default": 1, "Short": 2}

CHAT_MODES = {
    "Default": "default",
    "Learning Guide": "learning_guide",
    "Concise": "concise",
    "Detailed": "detailed",
}

ARTIFACT_TYPES = [
    "audio",
    "video",
    "report",
    "quiz",
    "flashcards",
    "infographic",
    "slide_deck",
    "data_table",
    "mind_map",
]

# Maps artifact type to download-friendly name
ARTIFACT_DL_TYPES = {
    "audio": "audio",
    "video": "video",
    "report": "report",
    "quiz": "quiz",
    "flashcards": "flashcards",
    "infographic": "infographic",
    "slide_deck": "slide_deck",
    "data_table": "data_table",
    "mind_map": "mind_map",
}


# ------------------------------------------------------------------ #
#  Helper: run blocking call in thread with GUI callback              #
# ------------------------------------------------------------------ #

def _run_async(frame, fn, args=(), kwargs=None, on_done=None, on_error=None, on_finally=None):
    """Run fn(*args, **kwargs) in a background thread, call on_done/on_error on GUI thread."""
    kwargs = kwargs or {}

    def _worker():
        try:
            result = fn(*args, **kwargs)
            if on_done:
                frame.after(0, on_done, result)
        except Exception as e:
            if on_error:
                frame.after(0, on_error, e)
            else:
                frame.after(0, lambda: messagebox.showerror("Error", str(e)))
        finally:
            if on_finally:
                frame.after(0, on_finally)

    threading.Thread(target=_worker, daemon=True).start()


# ------------------------------------------------------------------ #
#  NotebookLM Tab                                                     #
# ------------------------------------------------------------------ #

class NotebookLMTab:
    def __init__(self, parent):
        self.frame = ttk.Frame(parent, padding=5)
        self.notebooks = []       # list of Notebook objects
        self.sources = []         # list of Source objects
        self.artifacts = []       # list of Artifact objects
        self.selected_nb_id = None
        self.conversation_id = None

        # Audio player state
        self._ap_initialized = False
        self._ap_playing = False
        self._ap_paused = False
        self._ap_wav_path = None       # currently loaded WAV
        self._ap_audio_id = None       # artifact id of loaded audio
        self._ap_audio_title = None
        self._ap_duration_ms = 0
        self._ap_seek_offset_ms = 0    # offset passed to play(start=)
        self._ap_speed = 1.0
        self._ap_cache = Path(tempfile.gettempdir()) / "nlm_audio_cache"
        self._ap_cache.mkdir(exist_ok=True)
        self._ap_updating = False      # prevent seek feedback loop

        # Playback position memory
        self._ap_state_file = Path(__file__).parent / "playback_state.json"
        self._ap_positions = self._load_playback_state()

        self._build_ui()

    def _build_ui(self):
        f = self.frame

        # Top bar: auth
        auth_frame = ttk.Frame(f)
        auth_frame.pack(fill="x", pady=(0, 5))
        ttk.Button(auth_frame, text="Login (Browser)", command=self._login).pack(side="left", padx=2)
        self.auth_status = tk.StringVar(value="Not authenticated")
        ttk.Label(auth_frame, textvariable=self.auth_status, foreground="gray").pack(side="left", padx=10)
        ttk.Button(auth_frame, text="Refresh", command=self._refresh_all).pack(side="right", padx=2)

        # Main area: PanedWindow (left=notebooks/sources, right=actions)
        paned = ttk.PanedWindow(f, orient="horizontal")
        paned.pack(fill="both", expand=True)

        # --- LEFT PANEL: Notebooks & Sources ---
        left = ttk.Frame(paned, padding=5)
        paned.add(left, weight=1)

        # Notebooks section
        nb_frame = ttk.LabelFrame(left, text="Notebooks", padding=5)
        nb_frame.pack(fill="x")

        nb_btn_row = ttk.Frame(nb_frame)
        nb_btn_row.pack(fill="x")
        ttk.Button(nb_btn_row, text="List", command=self._list_notebooks, width=6).pack(side="left", padx=2)
        ttk.Button(nb_btn_row, text="Create", command=self._create_notebook, width=6).pack(side="left", padx=2)
        ttk.Button(nb_btn_row, text="Delete", command=self._delete_notebook, width=6).pack(side="left", padx=2)

        self.nb_listbox = tk.Listbox(nb_frame, height=5, exportselection=False)
        self.nb_listbox.pack(fill="x", pady=(5, 0))
        self.nb_listbox.bind("<<ListboxSelect>>", self._on_notebook_select)

        # Sources section
        src_frame = ttk.LabelFrame(left, text="Sources", padding=5)
        src_frame.pack(fill="x", pady=(8, 0))

        src_btn_row = ttk.Frame(src_frame)
        src_btn_row.pack(fill="x")
        ttk.Button(src_btn_row, text="Add URL", command=self._add_source_url, width=8).pack(side="left", padx=2)
        ttk.Button(src_btn_row, text="Add File", command=self._add_source_file, width=8).pack(side="left", padx=2)
        ttk.Button(src_btn_row, text="Add Text", command=self._add_source_text, width=8).pack(side="left", padx=2)
        ttk.Button(src_btn_row, text="Delete", command=self._delete_source, width=6).pack(side="left", padx=2)

        self.src_listbox = tk.Listbox(src_frame, height=4, exportselection=False)
        self.src_listbox.pack(fill="x", pady=(5, 0))

        # Artifacts section
        art_frame = ttk.LabelFrame(left, text="Generated Artifacts", padding=5)
        art_frame.pack(fill="x", pady=(8, 0))

        art_btn_row = ttk.Frame(art_frame)
        art_btn_row.pack(fill="x")
        ttk.Button(art_btn_row, text="Refresh", command=self._list_artifacts, width=8).pack(side="left", padx=2)
        ttk.Button(art_btn_row, text="Download", command=self._download_artifact, width=8).pack(side="left", padx=2)
        ttk.Button(art_btn_row, text="Delete", command=self._delete_artifact, width=6).pack(side="left", padx=2)

        self.art_listbox = tk.Listbox(art_frame, height=5, exportselection=False)
        self.art_listbox.pack(fill="both", expand=True, pady=(5, 0))
        self.art_listbox.bind("<Double-1>", lambda e: self._play_selected_artifact())

        # --- RIGHT PANEL: Tabbed actions ---
        right = ttk.Frame(paned, padding=5)
        paned.add(right, weight=2)

        action_nb = ttk.Notebook(right)
        action_nb.pack(fill="both", expand=True)

        # Generate tab
        gen_frame = ttk.Frame(action_nb, padding=10)
        action_nb.add(gen_frame, text="  Generate  ")
        self._build_generate_panel(gen_frame)

        # Chat tab
        chat_frame = ttk.Frame(action_nb, padding=10)
        action_nb.add(chat_frame, text="  Chat  ")
        self._build_chat_panel(chat_frame)

        # Status bar
        self.status_var = tk.StringVar(value="Login to get started.")
        ttk.Label(f, textvariable=self.status_var, foreground="gray").pack(fill="x", pady=(5, 0))

        # --- Audio Player (full width at bottom) ---
        self._build_audio_player(f)

    # ------------------------------------------------------------ #
    #  Generate panel                                                #
    # ------------------------------------------------------------ #

    def _build_generate_panel(self, parent):
        # Artifact type selector
        top = ttk.Frame(parent)
        top.pack(fill="x")

        ttk.Label(top, text="Artifact Type:").pack(side="left")
        self.artifact_type_var = tk.StringVar(value="")
        type_combo = ttk.Combobox(
            top, textvariable=self.artifact_type_var, width=15,
            values=ARTIFACT_TYPES, state="readonly"
        )
        type_combo.pack(side="left", padx=(5, 15))
        type_combo.bind("<<ComboboxSelected>>", self._on_artifact_type_change)

        ttk.Label(top, text="Language:").pack(side="left")
        self.gen_language_var = tk.StringVar(value="en")
        ttk.Entry(top, textvariable=self.gen_language_var, width=5).pack(side="left", padx=(5, 0))

        # Dynamic parameters frame
        self.params_frame = ttk.LabelFrame(parent, text="Parameters", padding=10)
        self.params_frame.pack(fill="x", pady=(10, 0))

        # Instructions / Prompt with save/load
        prompt_header = ttk.Frame(parent)
        prompt_header.pack(fill="x", pady=(10, 0))
        ttk.Label(prompt_header, text="Instructions / Prompt:").pack(side="left")

        self.saved_prompt_var = tk.StringVar()
        self.prompt_combo = ttk.Combobox(
            prompt_header, textvariable=self.saved_prompt_var, width=25, state="readonly"
        )
        self.prompt_combo.pack(side="left", padx=(10, 2))
        self.prompt_combo.bind("<<ComboboxSelected>>", self._load_selected_prompt)

        ttk.Button(prompt_header, text="Load", command=self._load_selected_prompt, width=5).pack(side="left", padx=1)
        ttk.Button(prompt_header, text="Save", command=self._save_prompt, width=5).pack(side="left", padx=1)
        ttk.Button(prompt_header, text="Delete", command=self._delete_prompt, width=6).pack(side="left", padx=1)

        self.gen_instructions = scrolledtext.ScrolledText(parent, wrap="word", height=4, width=50)
        self.gen_instructions.pack(fill="x", pady=(2, 0))

        # Generate button
        self.gen_btn = ttk.Button(parent, text="Generate", command=self._generate)
        self.gen_btn.pack(pady=(10, 0))

        # Load saved prompts and restore last-used
        self._prompts_file = Path(__file__).parent / "saved_prompts.json"
        self._saved_prompts = self._load_prompts_file()
        self._refresh_prompt_list()
        last_prompt = self._saved_prompts.get("__last_used__", "")
        if last_prompt:
            self.gen_instructions.insert("1.0", last_prompt)

        # Auto-process option
        self.auto_process_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            parent, text="Auto-process after download (clean PDF / transcribe audio)",
            variable=self.auto_process_var
        ).pack(anchor="w", pady=(5, 0))

        # Init parameter widgets for default type
        self._param_widgets = {}
        self._on_artifact_type_change()

    def _clear_params(self):
        for w in self.params_frame.winfo_children():
            w.destroy()
        self._param_widgets = {}

    def _add_param_combo(self, label, var_name, options, row, default=None):
        ttk.Label(self.params_frame, text=f"{label}:").grid(row=row, column=0, sticky="w", pady=2)
        var = tk.StringVar(value=default or list(options.keys())[0])
        combo = ttk.Combobox(
            self.params_frame, textvariable=var, width=18,
            values=list(options.keys()), state="readonly"
        )
        combo.grid(row=row, column=1, sticky="w", padx=(5, 0), pady=2)
        self._param_widgets[var_name] = (var, options)
        return var

    def _on_artifact_type_change(self, event=None):
        self._clear_params()
        atype = self.artifact_type_var.get()

        if not atype:
            ttk.Label(self.params_frame, text="Select an artifact type to see parameters.",
                      foreground="gray").grid(row=0, column=0)
            return

        if atype == "audio":
            self._add_param_combo("Format", "audio_format", AUDIO_FORMATS, 0, "Deep Dive")
            self._add_param_combo("Length", "audio_length", AUDIO_LENGTHS, 1, "Default")

        elif atype == "video":
            self._add_param_combo("Format", "video_format", VIDEO_FORMATS, 0, "Explainer")
            self._add_param_combo("Style", "video_style", VIDEO_STYLES, 1, "Auto Select")

        elif atype == "report":
            self._add_param_combo("Format", "report_format", REPORT_FORMATS, 0, "Briefing Doc")

        elif atype == "quiz":
            self._add_param_combo("Quantity", "quantity", QUIZ_QUANTITIES, 0, "Standard")
            self._add_param_combo("Difficulty", "difficulty", QUIZ_DIFFICULTIES, 1, "Medium")

        elif atype == "flashcards":
            self._add_param_combo("Quantity", "quantity", QUIZ_QUANTITIES, 0, "Standard")
            self._add_param_combo("Difficulty", "difficulty", QUIZ_DIFFICULTIES, 1, "Medium")

        elif atype == "infographic":
            self._add_param_combo("Orientation", "orientation", INFOGRAPHIC_ORIENTATIONS, 0, "Landscape")
            self._add_param_combo("Detail Level", "detail_level", INFOGRAPHIC_DETAILS, 1, "Standard")
            self._add_param_combo("Style", "style", INFOGRAPHIC_STYLES, 2, "Auto Select")

        elif atype == "slide_deck":
            self._add_param_combo("Format", "slide_format", SLIDE_FORMATS, 0, "Detailed Deck")
            self._add_param_combo("Length", "slide_length", SLIDE_LENGTHS, 1, "Default")

        elif atype == "data_table":
            ttk.Label(self.params_frame, text="No additional parameters.",
                      foreground="gray").grid(row=0, column=0)

        elif atype == "mind_map":
            ttk.Label(self.params_frame, text="No additional parameters.",
                      foreground="gray").grid(row=0, column=0)

    def _get_gen_params(self):
        """Build params dict from current widget values."""
        params = {}
        atype = self.artifact_type_var.get()

        # Language (for types that support it)
        if atype in ("audio", "video", "report", "infographic", "slide_deck", "data_table"):
            params["language"] = self.gen_language_var.get()

        # Instructions
        instructions = self.gen_instructions.get("1.0", "end").strip()
        if instructions:
            if atype == "report":
                params["extra_instructions"] = instructions
            else:
                params["instructions"] = instructions

        # Dynamic params from combos
        for param_name, (var, options) in self._param_widgets.items():
            selected_label = var.get()
            if selected_label in options:
                params[param_name] = options[selected_label]

        # Source IDs (use selected sources if any)
        selected_src_indices = self.src_listbox.curselection()
        if selected_src_indices:
            params["source_ids"] = [self.sources[i].id for i in selected_src_indices]

        return params

    # ------------------------------------------------------------ #
    #  Prompt management                                             #
    # ------------------------------------------------------------ #

    def _load_prompts_file(self):
        if self._prompts_file.exists():
            try:
                return json.loads(self._prompts_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        return {}

    def _save_prompts_file(self):
        self._prompts_file.write_text(
            json.dumps(self._saved_prompts, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def _refresh_prompt_list(self):
        names = sorted(k for k in self._saved_prompts if k != "__last_used__")
        self.prompt_combo["values"] = names
        if names and not self.saved_prompt_var.get():
            self.saved_prompt_var.set(names[0])

    def _load_selected_prompt(self, event=None):
        name = self.saved_prompt_var.get()
        if name and name in self._saved_prompts:
            self.gen_instructions.delete("1.0", "end")
            self.gen_instructions.insert("1.0", self._saved_prompts[name])

    def _save_prompt(self):
        text = self.gen_instructions.get("1.0", "end").strip()
        if not text:
            messagebox.showwarning("Empty", "Write some instructions first.")
            return
        name = tk.simpledialog.askstring("Save Prompt", "Prompt name:",
                                          initialvalue=self.saved_prompt_var.get() or "")
        if not name:
            return
        self._saved_prompts[name] = text
        self._save_prompts_file()
        self._refresh_prompt_list()
        self.saved_prompt_var.set(name)
        self.status_var.set(f"Prompt '{name}' saved.")

    def _delete_prompt(self):
        name = self.saved_prompt_var.get()
        if not name or name not in self._saved_prompts:
            return
        if not messagebox.askyesno("Confirm", f"Delete prompt '{name}'?"):
            return
        del self._saved_prompts[name]
        self._save_prompts_file()
        self.saved_prompt_var.set("")
        self._refresh_prompt_list()
        self.status_var.set(f"Prompt '{name}' deleted.")

    # ------------------------------------------------------------ #
    #  Chat panel                                                    #
    # ------------------------------------------------------------ #

    def _build_chat_panel(self, parent):
        # Chat mode
        mode_frame = ttk.Frame(parent)
        mode_frame.pack(fill="x")

        ttk.Label(mode_frame, text="Mode:").pack(side="left")
        self.chat_mode_var = tk.StringVar(value="Default")
        ttk.Combobox(
            mode_frame, textvariable=self.chat_mode_var, width=15,
            values=list(CHAT_MODES.keys()), state="readonly"
        ).pack(side="left", padx=(5, 0))
        ttk.Button(mode_frame, text="Set Mode", command=self._set_chat_mode, width=10).pack(side="left", padx=10)

        # Chat history
        self.chat_display = scrolledtext.ScrolledText(parent, wrap="word", height=14, width=60, state="disabled")
        self.chat_display.pack(fill="both", expand=True, pady=(8, 0))

        # Input
        input_frame = ttk.Frame(parent)
        input_frame.pack(fill="x", pady=(5, 0))

        self.chat_input = ttk.Entry(input_frame)
        self.chat_input.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.chat_input.bind("<Return>", lambda e: self._send_chat())

        ttk.Button(input_frame, text="Send", command=self._send_chat, width=8).pack(side="right")

    # ------------------------------------------------------------ #
    #  Auth actions                                                  #
    # ------------------------------------------------------------ #

    def _login(self):
        self.status_var.set("Opening browser — log in to Google, then wait...")

        def _do():
            import notebooklm_wrapper as w
            w.login()
            return True

        def _done(result):
            self.auth_status.set("Authenticated")
            self.status_var.set("Login successful! Click 'List' to load notebooks.")

        def _err(e):
            err_msg = str(e)
            self.status_var.set(f"Login failed: {err_msg}")
            # Suggest manual fallback
            messagebox.showerror(
                "Login Error",
                f"{err_msg}\n\n"
                "If this keeps failing, run this in your terminal:\n"
                "  notebooklm login\n\n"
                "Then click 'List' in the app."
            )

        _run_async(self.frame, _do, on_done=_done, on_error=_err)

    def _refresh_all(self):
        self._list_notebooks()

    # ------------------------------------------------------------ #
    #  Notebook actions                                              #
    # ------------------------------------------------------------ #

    def _list_notebooks(self):
        self.status_var.set("Loading notebooks...")

        def _done(nbs):
            self.notebooks = nbs or []
            self.nb_listbox.delete(0, "end")
            for nb in self.notebooks:
                self.nb_listbox.insert("end", f"{nb.title}  ({nb.sources_count} sources)")
            self.status_var.set(f"Loaded {len(self.notebooks)} notebooks.")

        def _err(e):
            self.status_var.set(f"Error: {e}")
            messagebox.showerror("Error", f"Failed to list notebooks:\n{e}")

        _run_async(self.frame,
                   lambda: __import__('notebooklm_wrapper').list_notebooks(),
                   on_done=_done, on_error=_err)

    def _create_notebook(self):
        title = tk.simpledialog.askstring("Create Notebook", "Notebook title:")
        if not title:
            return
        self.status_var.set(f"Creating '{title}'...")

        import notebooklm_wrapper as w

        def _done(nb):
            self.status_var.set(f"Created notebook: {nb.title}")
            self._list_notebooks()

        _run_async(self.frame, w.create_notebook, args=(title,), on_done=_done,
                   on_error=lambda e: self.status_var.set(f"Error: {e}"))

    def _delete_notebook(self):
        sel = self.nb_listbox.curselection()
        if not sel:
            return
        nb = self.notebooks[sel[0]]
        if not messagebox.askyesno("Confirm", f"Delete notebook '{nb.title}'?"):
            return

        import notebooklm_wrapper as w

        def _done(_):
            self.status_var.set(f"Deleted notebook.")
            self._list_notebooks()

        _run_async(self.frame, w.delete_notebook, args=(nb.id,), on_done=_done,
                   on_error=lambda e: self.status_var.set(f"Error: {e}"))

    def _on_notebook_select(self, event=None):
        sel = self.nb_listbox.curselection()
        if not sel:
            return
        nb = self.notebooks[sel[0]]
        self.selected_nb_id = nb.id
        self.conversation_id = None
        self._list_sources_for_nb(nb.id)
        self._list_artifacts_for_nb(nb.id)

    def _list_sources_for_nb(self, nb_id):
        import notebooklm_wrapper as w

        def _done(sources):
            self.sources = sources or []
            self.src_listbox.delete(0, "end")
            for s in self.sources:
                title = s.title or "(untitled)"
                self.src_listbox.insert("end", title)
            self.status_var.set(f"{len(self.sources)} sources loaded.")

        _run_async(self.frame, w.list_sources, args=(nb_id,), on_done=_done,
                   on_error=lambda e: self.status_var.set(f"Error: {e}"))

    def _list_artifacts_for_nb(self, nb_id):
        import notebooklm_wrapper as w

        def _done(artifacts):
            self.artifacts = artifacts or []
            self.art_listbox.delete(0, "end")
            for a in self.artifacts:
                self.art_listbox.insert("end", f"[{a.kind.value if hasattr(a, 'kind') else '?'}] {a.title}")

        _run_async(self.frame, w.list_artifacts, args=(nb_id,), on_done=_done,
                   on_error=lambda e: None)

    # ------------------------------------------------------------ #
    #  Source actions                                                 #
    # ------------------------------------------------------------ #

    def _add_source_url(self):
        if not self.selected_nb_id:
            messagebox.showwarning("No notebook", "Select a notebook first.")
            return
        url = tk.simpledialog.askstring("Add URL Source", "Enter URL (webpage or YouTube):")
        if not url:
            return
        self.status_var.set(f"Adding URL source...")
        import notebooklm_wrapper as w

        def _done(src):
            self.status_var.set(f"Added source: {src.title}")
            self._list_sources_for_nb(self.selected_nb_id)

        _run_async(self.frame, w.add_source_url,
                   args=(self.selected_nb_id, url), on_done=_done,
                   on_error=lambda e: self.status_var.set(f"Error: {e}"))

    def _add_source_file(self):
        if not self.selected_nb_id:
            messagebox.showwarning("No notebook", "Select a notebook first.")
            return
        path = filedialog.askopenfilename(
            title="Select source file",
            filetypes=[
                ("Supported files", "*.pdf *.docx *.md *.csv *.txt"),
                ("PDF", "*.pdf"),
                ("Word", "*.docx"),
                ("Markdown", "*.md"),
                ("CSV", "*.csv"),
                ("Text", "*.txt"),
            ],
        )
        if not path:
            return
        self.status_var.set(f"Uploading {os.path.basename(path)}...")
        import notebooklm_wrapper as w

        def _done(src):
            self.status_var.set(f"Added source: {src.title}")
            self._list_sources_for_nb(self.selected_nb_id)

        _run_async(self.frame, w.add_source_file,
                   args=(self.selected_nb_id, path), on_done=_done,
                   on_error=lambda e: self.status_var.set(f"Error: {e}"))

    def _add_source_text(self):
        if not self.selected_nb_id:
            messagebox.showwarning("No notebook", "Select a notebook first.")
            return

        dialog = tk.Toplevel(self.frame)
        dialog.title("Add Text Source")
        dialog.geometry("450x350")
        dialog.transient(self.frame)

        ttk.Label(dialog, text="Title:").pack(anchor="w", padx=10, pady=(10, 0))
        title_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=title_var, width=50).pack(padx=10, fill="x")

        ttk.Label(dialog, text="Content:").pack(anchor="w", padx=10, pady=(10, 0))
        text_area = scrolledtext.ScrolledText(dialog, wrap="word", height=12)
        text_area.pack(padx=10, fill="both", expand=True)

        def _submit():
            title = title_var.get().strip()
            content = text_area.get("1.0", "end").strip()
            if not title or not content:
                messagebox.showwarning("Missing", "Both title and content are required.")
                return
            dialog.destroy()
            self.status_var.set(f"Adding text source...")
            import notebooklm_wrapper as w

            def _done(src):
                self.status_var.set(f"Added source: {src.title}")
                self._list_sources_for_nb(self.selected_nb_id)

            _run_async(self.frame, w.add_source_text,
                       args=(self.selected_nb_id, title, content), on_done=_done,
                       on_error=lambda e: self.status_var.set(f"Error: {e}"))

        ttk.Button(dialog, text="Add Source", command=_submit).pack(pady=10)

    def _delete_source(self):
        sel = self.src_listbox.curselection()
        if not sel or not self.selected_nb_id:
            return
        src = self.sources[sel[0]]
        if not messagebox.askyesno("Confirm", f"Delete source '{src.title}'?"):
            return
        import notebooklm_wrapper as w

        def _done(_):
            self.status_var.set("Source deleted.")
            self._list_sources_for_nb(self.selected_nb_id)

        _run_async(self.frame, w.delete_source,
                   args=(self.selected_nb_id, src.id), on_done=_done,
                   on_error=lambda e: self.status_var.set(f"Error: {e}"))

    # ------------------------------------------------------------ #
    #  Artifact actions                                              #
    # ------------------------------------------------------------ #

    def _list_artifacts(self):
        if not self.selected_nb_id:
            return
        self._list_artifacts_for_nb(self.selected_nb_id)

    def _generate(self):
        if not self.selected_nb_id:
            messagebox.showwarning("No notebook", "Select a notebook first.")
            return

        atype = self.artifact_type_var.get()
        if not atype:
            messagebox.showwarning("No type", "Select an artifact type first.")
            return

        params = self._get_gen_params()

        # Remember current prompt for next session
        current_prompt = self.gen_instructions.get("1.0", "end").strip()
        self._saved_prompts["__last_used__"] = current_prompt
        self._save_prompts_file()

        self.status_var.set(f"Generating {atype}... (this may take a while)")

        import notebooklm_wrapper as w

        def _done(status):
            self.status_var.set(f"Generated {atype} successfully!")
            try:
                self._list_artifacts_for_nb(self.selected_nb_id)
            except Exception:
                pass

        def _err(e):
            self.status_var.set(f"Generation failed: {e}")
            messagebox.showerror("Generation Error", str(e))

        _run_async(self.frame, w.generate_artifact,
                   args=(self.selected_nb_id, atype, params),
                   on_done=_done, on_error=_err)

    def _download_artifact(self):
        sel = self.art_listbox.curselection()
        if not sel or not self.selected_nb_id:
            messagebox.showwarning("No selection", "Select an artifact to download.")
            return

        artifact = self.artifacts[sel[0]]
        folder = filedialog.askdirectory(title="Select download folder")
        if not folder:
            return

        # Determine artifact type for download
        atype_code = artifact._artifact_type if hasattr(artifact, '_artifact_type') else None
        type_map = {1: "audio", 2: "report", 3: "video", 4: "quiz", 5: "mind_map",
                    7: "infographic", 8: "slide_deck", 9: "data_table"}
        dl_type = type_map.get(atype_code, "report")

        # Determine file extension
        ext_map = {"audio": ".mp3", "video": ".mp4", "report": ".md", "quiz": ".json",
                   "flashcards": ".json", "infographic": ".png", "slide_deck": ".pdf",
                   "data_table": ".md", "mind_map": ".md"}
        ext = ext_map.get(dl_type, ".bin")
        safe_title = "".join(c if c.isalnum() or c in " -_" else "_" for c in artifact.title)
        output_path = os.path.join(folder, f"{safe_title}{ext}")

        self.status_var.set(f"Downloading {artifact.title}...")
        import notebooklm_wrapper as w

        def _done(path):
            self.status_var.set(f"Downloaded to: {path}")

            # Auto-process if enabled
            if self.auto_process_var.get():
                self._auto_process(path, dl_type)

        _run_async(self.frame, w.download_artifact,
                   args=(self.selected_nb_id, dl_type, output_path),
                   kwargs={"artifact_id": artifact.id},
                   on_done=_done,
                   on_error=lambda e: self.status_var.set(f"Download error: {e}"))

    def _auto_process(self, file_path, artifact_type):
        """Automatically process downloaded artifact."""
        if artifact_type == "slide_deck" and file_path.lower().endswith(".pdf"):
            self.status_var.set(f"Auto-processing: cleaning PDF & exporting PNGs...")
            # Switch to PDF tab would be ideal, but for now just run it
            messagebox.showinfo(
                "Auto-Process",
                f"Downloaded slide deck to:\n{file_path}\n\n"
                "Switch to the PDF Cleaner tab to clean and export as 4K PNGs."
            )
        elif artifact_type == "audio" and file_path.lower().endswith(".mp3"):
            messagebox.showinfo(
                "Auto-Process",
                f"Downloaded audio to:\n{file_path}\n\n"
                "Note: Audio Transcriber currently supports .m4a files.\n"
                "Convert to .m4a first, or switch to the Audio tab."
            )
        else:
            messagebox.showinfo("Downloaded", f"Saved to:\n{file_path}")

    def _delete_artifact(self):
        sel = self.art_listbox.curselection()
        if not sel or not self.selected_nb_id:
            return
        artifact = self.artifacts[sel[0]]
        if not messagebox.askyesno("Confirm", f"Delete artifact '{artifact.title}'?"):
            return
        import notebooklm_wrapper as w

        def _done(_):
            self.status_var.set("Artifact deleted.")
            self._list_artifacts_for_nb(self.selected_nb_id)

        _run_async(self.frame, w.delete_artifact,
                   args=(self.selected_nb_id, artifact.id), on_done=_done,
                   on_error=lambda e: self.status_var.set(f"Error: {e}"))

    # ------------------------------------------------------------ #
    #  Audio Player                                                  #
    # ------------------------------------------------------------ #

    def _build_audio_player(self, parent):
        """Build the audio player — full width bar at the bottom."""
        pf = ttk.LabelFrame(parent, text="Audio Player", padding=5)
        pf.pack(fill="x", pady=(5, 0))

        # Row 1: title + time
        row1 = ttk.Frame(pf)
        row1.pack(fill="x")
        self._ap_title_var = tk.StringVar(value="Double-click an [audio] artifact to play")
        ttk.Label(row1, textvariable=self._ap_title_var).pack(side="left")
        self._ap_time_var = tk.StringVar(value="")
        ttk.Label(row1, textvariable=self._ap_time_var).pack(side="right")

        # Row 2: seek bar
        self._ap_scale_var = tk.DoubleVar(value=0)
        self._ap_scale = ttk.Scale(pf, from_=0, to=1000, orient="horizontal",
                                    variable=self._ap_scale_var,
                                    command=self._ap_on_seek)
        self._ap_scale.pack(fill="x", pady=(2, 0))

        # Row 3: controls
        ctrl = ttk.Frame(pf)
        ctrl.pack(fill="x", pady=(2, 0))
        self._ap_play_btn = ttk.Button(ctrl, text="Play", command=self._ap_toggle, width=6)
        self._ap_play_btn.pack(side="left", padx=2)
        ttk.Button(ctrl, text="Stop", command=self._ap_stop, width=5).pack(side="left", padx=2)
        ttk.Label(ctrl, text="Speed:").pack(side="left", padx=(15, 2))
        self._ap_speed_var = tk.StringVar(value="1.0x")
        sc = ttk.Combobox(ctrl, textvariable=self._ap_speed_var, width=5,
                           values=["0.5x", "0.75x", "1.0x", "1.25x", "1.5x", "2.0x"],
                           state="readonly")
        sc.pack(side="left", padx=2)
        sc.bind("<<ComboboxSelected>>", self._ap_on_speed)

    # --- helpers ---

    def _ap_init(self):
        if self._ap_initialized:
            return True
        try:
            import pygame
            pygame.mixer.init(frequency=44100)
            self._ap_initialized = True
            return True
        except Exception as e:
            messagebox.showerror("Audio Error", f"Cannot init audio:\n{e}")
            return False

    def _load_playback_state(self):
        if self._ap_state_file.exists():
            try:
                return json.loads(self._ap_state_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}

    def _ap_save_positions(self):
        self._ap_state_file.write_text(
            json.dumps(self._ap_positions, indent=2, ensure_ascii=False), encoding="utf-8")

    def _ap_save_pos(self):
        if self._ap_audio_id and self._ap_duration_ms > 0:
            self._ap_positions[self._ap_audio_id] = {
                "pos": self._ap_current_ms(), "speed": self._ap_speed}
            self._ap_save_positions()

    def _ap_current_ms(self):
        """Current position in original-audio milliseconds."""
        if self._ap_playing and not self._ap_paused:
            import pygame
            # get_pos() = ms since play() was called (real time, not affected by speed)
            played_real_ms = pygame.mixer.music.get_pos()
            if played_real_ms < 0:
                played_real_ms = 0
            # In speed-adjusted file, real ms = original ms / speed
            original_ms = self._ap_seek_offset_ms + played_real_ms * self._ap_speed
            return min(original_ms, self._ap_duration_ms)
        return self._ap_seek_offset_ms

    @staticmethod
    def _ap_run_ffmpeg(cmd):
        import subprocess
        r = subprocess.run(cmd, capture_output=True, timeout=300)
        if r.returncode != 0:
            raise RuntimeError(r.stderr.decode(errors="replace")[-300:])

    def _ap_get_wav(self, raw_path, artifact_id, speed=1.0):
        """Convert raw -> WAV (at given speed). Returns WAV path. Cached."""
        suffix = "" if speed == 1.0 else f"_speed{speed:.2f}"
        wav = self._ap_cache / f"{artifact_id}{suffix}.wav"
        if wav.exists():
            return str(wav)
        cmd = ["ffmpeg", "-y", "-i", str(raw_path)]
        if speed != 1.0:
            cmd += ["-filter:a", f"atempo={speed}"]
        cmd += ["-ar", "44100", "-ac", "2", str(wav)]
        self._ap_run_ffmpeg(cmd)
        return str(wav)

    def _ap_get_duration(self, file_path):
        """Get duration in ms via ffprobe."""
        import subprocess
        r = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", file_path],
            capture_output=True, text=True, timeout=30)
        if r.returncode == 0 and r.stdout.strip():
            return int(float(r.stdout.strip()) * 1000)
        return 0

    def _ap_find_raw(self, artifact_id):
        """Find any cached raw/mp3 file for this artifact."""
        import glob as g
        for ext in ["*.raw", "*.mp3"]:
            hits = list(self._ap_cache.glob(f"{artifact_id}_*{ext.replace('*','')}"))
            if hits:
                return str(hits[0])
        return None

    # --- main actions ---

    def _play_selected_artifact(self):
        """Play the selected audio artifact."""
        sel = self.art_listbox.curselection()
        if not sel or not self.selected_nb_id:
            return
        # Check it's audio by listbox text
        text = self.art_listbox.get(sel[0])
        if not text.startswith("[audio]"):
            messagebox.showwarning("Not audio", "Select an [audio] artifact.")
            return

        artifact = self.artifacts[sel[0]]
        aid = artifact.id
        title = artifact.title

        # Already playing this one? Do nothing
        if aid == self._ap_audio_id and self._ap_playing:
            return

        # Stop current
        self._ap_stop()

        self._ap_audio_id = aid
        self._ap_audio_title = title
        self._ap_title_var.set(f"{title}  (loading...)")

        # Check cache for WAV at 1x speed
        raw = self._ap_find_raw(aid)
        wav_1x = self._ap_cache / f"{aid}.wav"

        if wav_1x.exists():
            self._ap_ready(str(wav_1x), aid, title)
            return

        if raw:
            # Convert in background
            self.status_var.set(f"Converting: {title}...")
            def _do():
                return self._ap_get_wav(raw, aid, 1.0)
            def _done(p):
                self.status_var.set("")
                self._ap_ready(p, aid, title)
            _run_async(self.frame, _do, on_done=_done,
                       on_error=lambda e: self._ap_title_var.set(f"Error: {e}"))
            return

        # Download then convert
        safe = "".join(c if c.isalnum() or c in " -_" else "_" for c in title)
        raw_path = str(self._ap_cache / f"{aid}_{safe}.raw")
        self.status_var.set(f"Downloading: {title}...")
        import notebooklm_wrapper as w

        def _downloaded(path):
            self.status_var.set(f"Converting: {title}...")
            def _do():
                return self._ap_get_wav(raw_path, aid, 1.0)
            def _done(p):
                self.status_var.set("")
                self._ap_ready(p, aid, title)
            _run_async(self.frame, _do, on_done=_done,
                       on_error=lambda e: self._ap_title_var.set(f"Error: {e}"))

        _run_async(self.frame, w.download_artifact,
                   args=(self.selected_nb_id, "audio", raw_path),
                   kwargs={"artifact_id": aid},
                   on_done=_downloaded,
                   on_error=lambda e: self._ap_title_var.set(f"Download error: {e}"))

    def _ap_ready(self, wav_1x_path, aid, title):
        """WAV at 1x is ready. Get duration, restore position, start playing."""
        if not self._ap_init():
            return

        self._ap_wav_path = wav_1x_path
        self._ap_audio_id = aid
        self._ap_audio_title = title

        # Duration from the 1x WAV
        self._ap_duration_ms = self._ap_get_duration(wav_1x_path)
        if self._ap_duration_ms == 0:
            # Fallback: compute from WAV size (44100 Hz, 2 ch, 16-bit)
            sz = os.path.getsize(wav_1x_path)
            self._ap_duration_ms = int((sz - 44) / 176400 * 1000)

        # Restore saved position & speed
        saved = self._ap_positions.get(aid, {})
        pos = saved.get("pos", 0)
        spd = saved.get("speed", 1.0)
        self._ap_speed = spd
        self._ap_speed_var.set(f"{spd}x")

        self._ap_title_var.set(title)
        self._ap_play_at(pos)

    def _ap_play_at(self, pos_ms):
        """Start playback from pos_ms (in original audio ms)."""
        import pygame

        speed = self._ap_speed
        # Get the WAV for this speed (may need to generate)
        if speed == 1.0:
            wav = self._ap_wav_path
        else:
            wav = self._ap_cache / f"{self._ap_audio_id}_speed{speed:.2f}.wav"
            if not wav.exists():
                # Generate synchronously (should be fast if 1x WAV exists)
                try:
                    raw = self._ap_find_raw(self._ap_audio_id) or self._ap_wav_path
                    self._ap_get_wav(raw, self._ap_audio_id, speed)
                except Exception as e:
                    self.status_var.set(f"Speed error: {e}")
                    wav = self._ap_wav_path
                    speed = 1.0
            wav = str(wav)

        try:
            pygame.mixer.music.load(wav)
            # In the speed-adjusted file, position maps differently
            start_sec = (pos_ms / 1000.0) / speed
            pygame.mixer.music.play(start=start_sec)

            self._ap_playing = True
            self._ap_paused = False
            self._ap_seek_offset_ms = pos_ms
            self._ap_play_btn.config(text="Pause")

            self._ap_tick()
        except Exception as e:
            self.status_var.set(f"Play error: {e}")

    def _ap_toggle(self):
        """Play / Pause toggle."""
        import pygame

        if not self._ap_wav_path:
            self._play_selected_artifact()
            return

        if self._ap_playing and not self._ap_paused:
            # Pause
            self._ap_save_pos()
            self._ap_seek_offset_ms = self._ap_current_ms()
            pygame.mixer.music.pause()
            self._ap_paused = True
            self._ap_playing = True  # still "loaded"
            self._ap_play_btn.config(text="Play")
        elif self._ap_paused:
            # Unpause
            pygame.mixer.music.unpause()
            self._ap_paused = False
            self._ap_play_btn.config(text="Pause")
            self._ap_tick()
        else:
            # Start from saved offset
            self._ap_play_at(self._ap_seek_offset_ms)

    def _ap_stop(self):
        """Stop playback, save position."""
        if self._ap_initialized:
            try:
                import pygame
                if self._ap_playing:
                    self._ap_save_pos()
                pygame.mixer.music.stop()
            except Exception:
                pass
        self._ap_playing = False
        self._ap_paused = False
        self._ap_play_btn.config(text="Play")

    def _ap_on_seek(self, value):
        """Seek bar dragged."""
        if self._ap_updating or self._ap_duration_ms == 0:
            return
        target_ms = (float(value) / 1000.0) * self._ap_duration_ms
        if self._ap_playing and not self._ap_paused:
            self._ap_play_at(target_ms)
        else:
            self._ap_seek_offset_ms = target_ms
            self._ap_update_time(target_ms)

    def _ap_on_speed(self, event=None):
        """Speed combo changed."""
        try:
            new_speed = float(self._ap_speed_var.get().replace("x", ""))
        except ValueError:
            return
        if new_speed == self._ap_speed:
            return

        pos = self._ap_current_ms()
        was_playing = self._ap_playing and not self._ap_paused

        if self._ap_initialized:
            try:
                import pygame
                pygame.mixer.music.stop()
            except Exception:
                pass
        self._ap_playing = False
        self._ap_paused = False
        self._ap_speed = new_speed
        self._ap_seek_offset_ms = pos

        if was_playing:
            self._ap_play_at(pos)
        else:
            self._ap_save_pos()

    def _ap_tick(self):
        """Update UI every 500ms while playing."""
        if not self._ap_playing or self._ap_paused:
            return

        import pygame
        pos = self._ap_current_ms()

        if not pygame.mixer.music.get_busy():
            # Finished
            self._ap_playing = False
            self._ap_seek_offset_ms = 0
            self._ap_play_btn.config(text="Play")
            self._ap_scale_var.set(0)
            self._ap_update_time(0)
            self._ap_positions.pop(self._ap_audio_id, None)
            self._ap_save_positions()
            return

        if self._ap_duration_ms > 0:
            self._ap_updating = True
            self._ap_scale_var.set((pos / self._ap_duration_ms) * 1000)
            self._ap_updating = False
        self._ap_update_time(pos)
        self.frame.after(500, self._ap_tick)

    def _ap_update_time(self, pos_ms):
        t = self._fmt(pos_ms)
        d = self._fmt(self._ap_duration_ms)
        s = f" ({self._ap_speed}x)" if self._ap_speed != 1.0 else ""
        self._ap_time_var.set(f"{t} / {d}{s}")

    @staticmethod
    def _fmt(ms):
        s = int(ms / 1000)
        h, s = divmod(s, 3600)
        m, s = divmod(s, 60)
        return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

    # ------------------------------------------------------------ #
    #  Chat actions                                                  #
    # ------------------------------------------------------------ #

    def _set_chat_mode(self):
        if not self.selected_nb_id:
            return
        mode = CHAT_MODES.get(self.chat_mode_var.get(), "default")
        import notebooklm_wrapper as w
        _run_async(self.frame, w.configure_chat,
                   args=(self.selected_nb_id,),
                   kwargs={"mode": mode},
                   on_done=lambda _: self.status_var.set(f"Chat mode set to: {self.chat_mode_var.get()}"),
                   on_error=lambda e: self.status_var.set(f"Error: {e}"))

    def _send_chat(self):
        if not self.selected_nb_id:
            messagebox.showwarning("No notebook", "Select a notebook first.")
            return
        question = self.chat_input.get().strip()
        if not question:
            return

        self.chat_input.delete(0, "end")
        self._append_chat(f"You: {question}\n\n")
        self.status_var.set("Thinking...")

        # Use selected sources if any
        src_indices = self.src_listbox.curselection()
        source_ids = [self.sources[i].id for i in src_indices] if src_indices else None

        import notebooklm_wrapper as w

        def _done(result):
            self.conversation_id = result.conversation_id
            answer = result.answer

            # Add citations
            if result.references:
                answer += "\n\nReferences:"
                for ref in result.references:
                    cite_num = ref.citation_number or "?"
                    cite_text = (ref.cited_text or "")[:100]
                    answer += f"\n  [{cite_num}] {cite_text}"

            self._append_chat(f"NotebookLM: {answer}\n\n{'='*50}\n\n")
            self.status_var.set("Response received.")

        def _err(e):
            self._append_chat(f"Error: {e}\n\n")
            self.status_var.set(f"Chat error: {e}")

        _run_async(self.frame, w.chat_ask,
                   args=(self.selected_nb_id, question),
                   kwargs={"source_ids": source_ids, "conversation_id": self.conversation_id},
                   on_done=_done, on_error=_err)

    def _append_chat(self, text):
        self.chat_display.config(state="normal")
        self.chat_display.insert("end", text)
        self.chat_display.see("end")
        self.chat_display.config(state="disabled")
