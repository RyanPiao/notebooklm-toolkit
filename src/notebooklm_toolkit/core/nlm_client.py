#!/usr/bin/env python3
"""
NotebookLM Client — Async wrapper for notebooklm-py.

Direct async functions for use with FastAPI routes.
No AsyncBridge needed — FastAPI is async-native.
"""

from pathlib import Path
from typing import Optional


def get_storage_path() -> Path:
    import os
    home = Path(os.environ.get("NOTEBOOKLM_HOME", Path.home() / ".notebooklm"))
    return home / "storage_state.json"


def login():
    """Run the browser login flow (blocking, opens Playwright browser)."""
    from playwright.sync_api import sync_playwright

    storage_path = get_storage_path()
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    profile_dir = storage_path.parent / "browser_profile"
    profile_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            channel="chrome",
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
            ignore_default_args=["--enable-automation"],
        )
        page = browser.pages[0] if browser.pages else browser.new_page()
        page.goto("https://notebooklm.google.com/")
        try:
            page.wait_for_url("**/notebooklm.google.com/**", timeout=300000)
            page.wait_for_timeout(3000)
            for _ in range(60):
                if "accounts.google.com" not in page.url:
                    page.wait_for_timeout(2000)
                    break
                page.wait_for_timeout(5000)
        except Exception:
            pass
        browser.storage_state(path=str(storage_path))
        browser.close()

    if not storage_path.exists():
        raise FileNotFoundError(f"Login failed — storage file not created at {storage_path}")


async def _get_client(auth_path=None):
    from notebooklm import NotebookLMClient
    return await NotebookLMClient.from_storage(path=auth_path)


async def list_notebooks(auth_path=None):
    async with await _get_client(auth_path) as client:
        return await client.notebooks.list()


async def create_notebook(title, auth_path=None):
    async with await _get_client(auth_path) as client:
        return await client.notebooks.create(title)


async def delete_notebook(notebook_id, auth_path=None):
    async with await _get_client(auth_path) as client:
        return await client.notebooks.delete(notebook_id)


async def list_sources(notebook_id, auth_path=None):
    async with await _get_client(auth_path) as client:
        return await client.sources.list(notebook_id)


async def add_source_url(notebook_id, url, auth_path=None):
    async with await _get_client(auth_path) as client:
        return await client.sources.add_url(notebook_id, url, wait=True)


async def add_source_text(notebook_id, title, content, auth_path=None):
    async with await _get_client(auth_path) as client:
        return await client.sources.add_text(notebook_id, title, content, wait=True)


async def add_source_file(notebook_id, file_path, auth_path=None):
    async with await _get_client(auth_path) as client:
        return await client.sources.add_file(notebook_id, file_path, wait=True)


async def delete_source(notebook_id, source_id, auth_path=None):
    async with await _get_client(auth_path) as client:
        return await client.sources.delete(notebook_id, source_id)


async def generate_artifact(notebook_id, artifact_type, params, auth_path=None):
    async with await _get_client(auth_path) as client:
        gen_fn = getattr(client.artifacts, f"generate_{artifact_type}")
        status = await gen_fn(notebook_id, **params)
        if artifact_type == "mind_map":
            return status
        try:
            completed = await client.artifacts.wait_for_completion(
                notebook_id, status.task_id, timeout=300
            )
            return completed
        except Exception:
            return status


async def list_artifacts(notebook_id, artifact_type=None, auth_path=None):
    async with await _get_client(auth_path) as client:
        if artifact_type:
            list_fn = getattr(client.artifacts, f"list_{artifact_type}", None)
            if list_fn:
                return await list_fn(notebook_id)
        return await client.artifacts.list(notebook_id)


async def download_artifact(notebook_id, artifact_type, output_path, artifact_id=None, auth_path=None, **kwargs):
    async with await _get_client(auth_path) as client:
        dl_fn = getattr(client.artifacts, f"download_{artifact_type}")
        dl_kwargs = {"notebook_id": notebook_id, "output_path": output_path}
        if artifact_id:
            dl_kwargs["artifact_id"] = artifact_id
        dl_kwargs.update(kwargs)
        return await dl_fn(**dl_kwargs)


async def delete_artifact(notebook_id, artifact_id, auth_path=None):
    async with await _get_client(auth_path) as client:
        return await client.artifacts.delete(notebook_id, artifact_id)


async def chat_ask(notebook_id, question, source_ids=None, conversation_id=None, auth_path=None):
    async with await _get_client(auth_path) as client:
        return await client.chat.ask(
            notebook_id, question,
            source_ids=source_ids,
            conversation_id=conversation_id,
        )


async def configure_chat(notebook_id, mode=None, auth_path=None):
    async with await _get_client(auth_path) as client:
        if mode:
            await client.chat.set_mode(notebook_id, mode)
