#!/usr/bin/env python3
"""
NotebookLM async-to-sync bridge for tkinter GUI.

Runs an asyncio event loop in a background thread and provides
synchronous wrappers that schedule async calls and return results.
"""

import asyncio
import threading
from typing import Any, Callable, Optional
from pathlib import Path


class AsyncBridge:
    """Manages a background asyncio event loop for async API calls."""

    def __init__(self):
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._client = None

    def start(self):
        """Start the background event loop thread."""
        if self._thread and self._thread.is_alive():
            return
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def _run_loop(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def stop(self):
        """Stop the background event loop."""
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread:
            self._thread.join(timeout=5)

    def run(self, coro) -> Any:
        """Run an async coroutine and return its result (blocking)."""
        if not self._loop:
            self.start()
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result(timeout=600)  # 10 min timeout for long operations

    def run_in_thread(self, coro, callback: Callable, error_callback: Callable = None):
        """
        Run an async coroutine in background, call callback with result on completion.
        Callbacks are called from the background thread — caller must use
        widget.after() to post to GUI thread.
        """
        if not self._loop:
            self.start()

        def _wrapper():
            try:
                future = asyncio.run_coroutine_threadsafe(coro, self._loop)
                result = future.result(timeout=600)
                callback(result)
            except Exception as e:
                if error_callback:
                    error_callback(e)
                else:
                    callback(None)

        threading.Thread(target=_wrapper, daemon=True).start()


# Singleton bridge instance
_bridge = AsyncBridge()


def get_bridge() -> AsyncBridge:
    """Get the shared AsyncBridge instance."""
    if not _bridge._loop:
        _bridge.start()
    return _bridge


async def _get_client(auth_path: Optional[str] = None):
    """Get or create the NotebookLM client."""
    from notebooklm import NotebookLMClient
    return await NotebookLMClient.from_storage(path=auth_path)


# ------------------------------------------------------------------ #
#  Sync wrapper functions                                             #
# ------------------------------------------------------------------ #

def login():
    """Run the browser login flow (blocking, opens browser)."""
    import subprocess
    import sys
    subprocess.run([sys.executable, "-m", "notebooklm", "login"], check=True)


def list_notebooks(auth_path=None):
    bridge = get_bridge()
    async def _do():
        async with await _get_client(auth_path) as client:
            return await client.notebooks.list()
    return bridge.run(_do())


def create_notebook(title, auth_path=None):
    bridge = get_bridge()
    async def _do():
        async with await _get_client(auth_path) as client:
            return await client.notebooks.create(title)
    return bridge.run(_do())


def delete_notebook(notebook_id, auth_path=None):
    bridge = get_bridge()
    async def _do():
        async with await _get_client(auth_path) as client:
            return await client.notebooks.delete(notebook_id)
    return bridge.run(_do())


def list_sources(notebook_id, auth_path=None):
    bridge = get_bridge()
    async def _do():
        async with await _get_client(auth_path) as client:
            return await client.sources.list(notebook_id)
    return bridge.run(_do())


def add_source_url(notebook_id, url, auth_path=None):
    bridge = get_bridge()
    async def _do():
        async with await _get_client(auth_path) as client:
            return await client.sources.add_url(notebook_id, url, wait=True)
    return bridge.run(_do())


def add_source_text(notebook_id, title, content, auth_path=None):
    bridge = get_bridge()
    async def _do():
        async with await _get_client(auth_path) as client:
            return await client.sources.add_text(notebook_id, title, content, wait=True)
    return bridge.run(_do())


def add_source_file(notebook_id, file_path, auth_path=None):
    bridge = get_bridge()
    async def _do():
        async with await _get_client(auth_path) as client:
            return await client.sources.add_file(notebook_id, file_path, wait=True)
    return bridge.run(_do())


def delete_source(notebook_id, source_id, auth_path=None):
    bridge = get_bridge()
    async def _do():
        async with await _get_client(auth_path) as client:
            return await client.sources.delete(notebook_id, source_id)
    return bridge.run(_do())


def generate_artifact(notebook_id, artifact_type, params, auth_path=None):
    """
    Generate an artifact. Returns GenerationStatus.

    artifact_type: 'audio', 'video', 'report', 'quiz', 'flashcards',
                   'infographic', 'slide_deck', 'data_table', 'mind_map'
    params: dict of parameters for the specific artifact type
    """
    bridge = get_bridge()
    async def _do():
        async with await _get_client(auth_path) as client:
            gen_fn = getattr(client.artifacts, f"generate_{artifact_type}")
            status = await gen_fn(notebook_id, **params)
            if artifact_type == "mind_map":
                return status  # mind_map returns dict directly
            completed = await client.artifacts.wait_for_completion(
                notebook_id, status.task_id, timeout=600
            )
            return completed
    return bridge.run(_do())


def list_artifacts(notebook_id, artifact_type=None, auth_path=None):
    bridge = get_bridge()
    async def _do():
        async with await _get_client(auth_path) as client:
            if artifact_type:
                list_fn = getattr(client.artifacts, f"list_{artifact_type}", None)
                if list_fn:
                    return await list_fn(notebook_id)
            return await client.artifacts.list(notebook_id)
    return bridge.run(_do())


def download_artifact(notebook_id, artifact_type, output_path, artifact_id=None, auth_path=None, **kwargs):
    """Download an artifact to a file."""
    bridge = get_bridge()
    async def _do():
        async with await _get_client(auth_path) as client:
            dl_fn = getattr(client.artifacts, f"download_{artifact_type}")
            dl_kwargs = {"notebook_id": notebook_id, "output_path": output_path}
            if artifact_id:
                dl_kwargs["artifact_id"] = artifact_id
            dl_kwargs.update(kwargs)
            return await dl_fn(**dl_kwargs)
    return bridge.run(_do())


def delete_artifact(notebook_id, artifact_id, auth_path=None):
    bridge = get_bridge()
    async def _do():
        async with await _get_client(auth_path) as client:
            return await client.artifacts.delete(notebook_id, artifact_id)
    return bridge.run(_do())


def chat_ask(notebook_id, question, source_ids=None, conversation_id=None, auth_path=None):
    bridge = get_bridge()
    async def _do():
        async with await _get_client(auth_path) as client:
            return await client.chat.ask(
                notebook_id, question,
                source_ids=source_ids,
                conversation_id=conversation_id,
            )
    return bridge.run(_do())


def chat_history(notebook_id, auth_path=None):
    bridge = get_bridge()
    async def _do():
        async with await _get_client(auth_path) as client:
            return await client.chat.get_history(notebook_id)
    return bridge.run(_do())


def configure_chat(notebook_id, mode=None, auth_path=None):
    bridge = get_bridge()
    async def _do():
        async with await _get_client(auth_path) as client:
            if mode:
                await client.chat.set_mode(notebook_id, mode)
    return bridge.run(_do())
