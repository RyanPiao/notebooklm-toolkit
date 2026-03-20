#!/usr/bin/env python3
"""
NotebookLM GUI Tab — Full integration with notebooklm-py.

Provides notebook management, source management, artifact generation
with all parameters, chat, and download with auto-processing.
"""

import os
import threading
import tkinter as tk
import tkinter.simpledialog
from tkinter import ttk, filedialog, messagebox, scrolledtext


# ------------------------------------------------------------------ #
#  Enum display mappings                                              #
# ------------------------------------------------------------------ #

AUDIO_FORMATS = {
    "Deep Dive": 1,
    "Brief": 2,
    "Critique": 3,
    "Debate": 4,
}

AUDIO_LENGTHS = {
    "Short": 1,
    "Default": 2,
    "Long": 3,
}

VIDEO_FORMATS = {
    "Explainer": 1,
    "Brief": 2,
    "Cinematic": 3,
}

VIDEO_STYLES = {
    "Auto Select": 1,
    "Custom": 2,
    "Classic": 3,
    "Whiteboard": 4,
    "Kawaii": 5,
    "Anime": 6,
    "Watercolor": 7,
    "Retro Print": 8,
    "Heritage": 9,
    "Paper Craft": 10,
}

REPORT_FORMATS = {
    "Briefing Doc": "briefing_doc",
    "Study Guide": "study_guide",
    "Blog Post": "blog_post",
    "Custom": "custom",
}

QUIZ_QUANTITIES = {
    "Fewer": 1,
    "Standard": 2,
    "More": 2,
}

QUIZ_DIFFICULTIES = {
    "Easy": 1,
    "Medium": 2,
    "Hard": 3,
}

INFOGRAPHIC_ORIENTATIONS = {
    "Landscape": 1,
    "Portrait": 2,
    "Square": 3,
}

INFOGRAPHIC_DETAILS = {
    "Concise": 1,
    "Standard": 2,
    "Detailed": 3,
}

INFOGRAPHIC_STYLES = {
    "Auto Select": 1,
    "Sketch Note": 2,
    "Professional": 3,
    "Bento Grid": 4,
    "Editorial": 5,
    "Instructional": 6,
    "Bricks": 7,
    "Clay": 8,
    "Anime": 9,
    "Kawaii": 10,
    "Scientific": 11,
}

SLIDE_FORMATS = {
    "Detailed Deck": 1,
    "Presenter Slides": 2,
}

SLIDE_LENGTHS = {
    "Default": 1,
    "Short": 2,
}

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

def _run_async(frame, fn, args=(), kwargs=None, on_done=None, on_error=None):
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

        self.nb_listbox = tk.Listbox(nb_frame, height=6, exportselection=False)
        self.nb_listbox.pack(fill="x", pady=(5, 0))
        self.nb_listbox.bind("<<ListboxSelect>>", self._on_notebook_select)

        # Sources section
        src_frame = ttk.LabelFrame(left, text="Sources", padding=5)
        src_frame.pack(fill="both", expand=True, pady=(8, 0))

        src_btn_row = ttk.Frame(src_frame)
        src_btn_row.pack(fill="x")
        ttk.Button(src_btn_row, text="Add URL", command=self._add_source_url, width=8).pack(side="left", padx=2)
        ttk.Button(src_btn_row, text="Add File", command=self._add_source_file, width=8).pack(side="left", padx=2)
        ttk.Button(src_btn_row, text="Add Text", command=self._add_source_text, width=8).pack(side="left", padx=2)
        ttk.Button(src_btn_row, text="Delete", command=self._delete_source, width=6).pack(side="left", padx=2)

        self.src_listbox = tk.Listbox(src_frame, height=6, exportselection=False)
        self.src_listbox.pack(fill="both", expand=True, pady=(5, 0))

        # Artifacts section
        art_frame = ttk.LabelFrame(left, text="Generated Artifacts", padding=5)
        art_frame.pack(fill="x", pady=(8, 0))

        art_btn_row = ttk.Frame(art_frame)
        art_btn_row.pack(fill="x")
        ttk.Button(art_btn_row, text="Refresh", command=self._list_artifacts, width=8).pack(side="left", padx=2)
        ttk.Button(art_btn_row, text="Download", command=self._download_artifact, width=8).pack(side="left", padx=2)
        ttk.Button(art_btn_row, text="Delete", command=self._delete_artifact, width=6).pack(side="left", padx=2)

        self.art_listbox = tk.Listbox(art_frame, height=5, exportselection=False)
        self.art_listbox.pack(fill="x", pady=(5, 0))

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

    # ------------------------------------------------------------ #
    #  Generate panel                                                #
    # ------------------------------------------------------------ #

    def _build_generate_panel(self, parent):
        # Artifact type selector
        top = ttk.Frame(parent)
        top.pack(fill="x")

        ttk.Label(top, text="Artifact Type:").pack(side="left")
        self.artifact_type_var = tk.StringVar(value="audio")
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

        # Instructions
        ttk.Label(parent, text="Instructions / Prompt:").pack(anchor="w", pady=(10, 0))
        self.gen_instructions = scrolledtext.ScrolledText(parent, wrap="word", height=4, width=50)
        self.gen_instructions.pack(fill="x", pady=(2, 0))

        # Generate button
        self.gen_btn = ttk.Button(parent, text="Generate", command=self._generate)
        self.gen_btn.pack(pady=(10, 0))

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
        self.status_var.set("Opening browser for Google login...")
        def _do():
            import notebooklm_wrapper as w
            w.login()

        def _done(result):
            self.auth_status.set("Authenticated")
            self.status_var.set("Login successful. Click 'List' to load notebooks.")

        def _err(e):
            self.status_var.set(f"Login failed: {e}")
            messagebox.showerror("Login Error", str(e))

        _run_async(self.frame, lambda: _do(), on_done=_done, on_error=_err)

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
        params = self._get_gen_params()
        self.status_var.set(f"Generating {atype}... (this may take a while)")
        self.gen_btn.config(state="disabled")

        import notebooklm_wrapper as w

        def _done(status):
            self.gen_btn.config(state="normal")
            self.status_var.set(f"Generated {atype} successfully!")
            self._list_artifacts_for_nb(self.selected_nb_id)

        def _err(e):
            self.gen_btn.config(state="normal")
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
