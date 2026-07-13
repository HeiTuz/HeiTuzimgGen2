#!/usr/bin/env python3
"""Execute one complete apparel candidate set in one direct browser GPT session.

Dry-run is the default.  Live mode reuses the same CDP/Playwright/login/model
surface as browser adapter, attaches the complete source folder and immutable
folder contract in one upload operation, and recovers only images observed in
that session after the corresponding output request.
"""
from __future__ import annotations

import argparse
import base64
import importlib.util
import io
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
CORE_PATH = HERE / "apparel_three_fullset.py"
BROWSER_ADAPTER_PATH = Path(os.environ.get("HEITUZ_BROWSER_ADAPTER_SCRIPT", "")).expanduser()
APPROVAL_ENV = "HERMES_APPAREL_BROWSER_GPT_APPROVED_SHA256"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


core = _load_module("heituz_apparel_three_fullset", CORE_PATH)


class BrowserTaskError(RuntimeError):
    pass


def _load_task(spec_path: Path) -> tuple[dict[str, Any], dict[str, Any], Path]:
    spec = core.read_json(spec_path)
    shared_path = Path(spec.get("shared_contract_path", "")).resolve()
    shared = core.read_json(shared_path)
    digest = core.sha256_bytes(core._canonical(shared))
    if digest != spec.get("shared_contract_sha256"):
        raise BrowserTaskError("shared folder contract hash mismatch")
    stored_shared = shared
    shared = core.validate_folder_contract({
        **stored_shared,
        "sources": [s["name"] if isinstance(s, dict) else s for s in stored_shared["sources"]],
    }) if stored_shared.get("sources") and isinstance(stored_shared["sources"][0], dict) else core.validate_folder_contract(stored_shared)
    if core._canonical(shared) != core._canonical(stored_shared):
        raise BrowserTaskError("immutable shared source inventory changed after preparation")
    candidate_sets = core.candidate_sets_for_shared_contract(shared)
    if spec.get("candidate_set") not in candidate_sets:
        raise BrowserTaskError("invalid candidate_set")
    if spec.get("candidate_sets") != list(candidate_sets) or spec.get("task_count") != len(candidate_sets):
        raise BrowserTaskError("task spec does not match dynamic candidate-set contract")
    expected_task_id = f"task-{candidate_sets.index(spec['candidate_set']) + 1}"
    if spec.get("task_id") != expected_task_id:
        raise BrowserTaskError("task id does not match dynamic candidate-set contract")
    candidate_root = Path(spec["candidate_root"]).resolve()
    expected = shared_path.parent / spec["candidate_set"]
    if candidate_root != expected:
        raise BrowserTaskError("candidate root does not match disjoint set ownership")
    candidate_root.mkdir(parents=True, exist_ok=True)
    return spec, shared, candidate_root


def _atomic_json(path: Path, data: Any) -> None:
    core.atomic_json(path, data)


def _verified_resume(output: Path, row: dict[str, Any] | None) -> bool:
    return bool(output.is_file() and row and row.get("sha256") == core.sha256_file(output) and row.get("size") == output.stat().st_size)


def _input_inventory(shared: dict[str, Any]) -> list[Path]:
    paths = [Path(source["path"]).resolve() for source in shared["sources"]]
    if len(paths) != len(shared["sources"]) or any(not p.is_file() for p in paths):
        raise BrowserTaskError("complete source inventory is unavailable")
    return paths


def dry_run(spec_path: Path) -> dict[str, Any]:
    spec, shared, candidate_root = _load_task(spec_path)
    outputs = [
        {"id": o["id"], "filename": o["filename"], "path": str(candidate_root / o["filename"])}
        for o in shared["outputs"]
    ]
    return {
        "live": False,
        "task_id": spec["task_id"],
        "candidate_set": spec["candidate_set"],
        "browser_surface": "browser adapter direct CDP/Playwright session",
        "shared_contract_sha256": spec["shared_contract_sha256"],
        "approval_env": APPROVAL_ENV,
        "source_count": len(_input_inventory(shared)),
        "source_inventory": [s["name"] for s in shared["sources"]],
        "complete_output_inventory": outputs,
        "invariants": {
            "one_browser_session": True,
            "all_sources_uploaded_together": True,
            "generated_result_chaining": False,
            "cross_session_recovery": False,
            "overwrite": False,
            "provider_fallback": False,
        },
    }


def _visible_chip(page, name: str) -> bool:
    stem = Path(name).stem[:12]
    try:
        composer = page.locator("form:has(#prompt-textarea), [role='presentation']:has(#prompt-textarea)").first
        return composer.get_by_text(stem, exact=False).count() > 0
    except Exception:
        return False


def _attach_all_once(page, files: list[Path]) -> None:
    inp = page.query_selector("input[type=file]")
    if not inp:
        raise BrowserTaskError("browser GPT file input not found")
    inp.set_input_files([str(p) for p in files])
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        if all(_visible_chip(page, p.name) for p in files):
            return
        time.sleep(1)
    missing = [p.name for p in files if not _visible_chip(page, p.name)]
    raise BrowserTaskError(f"complete simultaneous upload not verified: {missing}")


def _assistant_image_sources(page) -> set[str]:
    selectors = [
        '[data-message-author-role="assistant"] img[src]',
        'article[data-testid^="conversation-turn"] img[src]',
    ]
    result: set[str] = set()
    for selector in selectors:
        try:
            for image in page.query_selector_all(selector):
                src = image.get_attribute("src") or ""
                if src and not any(bad in src.lower() for bad in ("avatar", "emoji", "icon")):
                    result.add(src)
        except Exception:
            continue
    return result


def _read_url_bytes(page, src: str) -> bytes:
    script = """async (url) => {
      const response = await fetch(url, {credentials: 'include'});
      if (!response.ok) throw new Error(`image fetch ${response.status}`);
      const bytes = new Uint8Array(await response.arrayBuffer());
      let binary = ''; const step = 0x8000;
      for (let i=0; i<bytes.length; i+=step) binary += String.fromCharCode(...bytes.subarray(i, i+step));
      return btoa(binary);
    }"""
    encoded = page.evaluate(script, src)
    data = base64.b64decode(encoded, validate=True)
    if not data:
        raise BrowserTaskError("fresh browser image was empty")
    return data


def _write_png_exclusive(path: Path, raw: bytes) -> None:
    try:
        from PIL import Image
    except ImportError as exc:
        raise BrowserTaskError("Pillow is required to normalize browser results to PNG") from exc
    path.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(io.BytesIO(raw)) as image:
        image.load()
        with path.open("xb") as fh:
            image.save(fh, format="PNG")
            fh.flush()
            os.fsync(fh.fileno())
    if path.stat().st_size <= 0:
        raise BrowserTaskError("normalized PNG is empty")


def _send_and_recover(page, browser_adapter, prompt: str, output: Path, timeout: int) -> tuple[str, str]:
    baseline_sources = _assistant_image_sources(page)
    baseline_users = browser_adapter.count_msgs(page, browser_adapter.USER_MSG_SELECTOR)
    browser_adapter.clear_composer(page)
    browser_adapter.put_text(page, prompt)
    if not browser_adapter.composer_has_prompt(page, prompt):
        raise BrowserTaskError("prompt composer verification failed")
    browser_adapter.click_send(page)
    sent_deadline = time.monotonic() + 30
    while time.monotonic() < sent_deadline:
        if browser_adapter.count_msgs(page, browser_adapter.USER_MSG_SELECTOR) > baseline_users:
            break
        time.sleep(1)
    else:
        raise BrowserTaskError("browser prompt was not submitted")

    deadline = time.monotonic() + timeout
    stable_src = None
    stable_since = None
    while time.monotonic() < deadline:
        fresh = sorted(_assistant_image_sources(page) - baseline_sources)
        if fresh and not browser_adapter.is_streaming(page):
            current = fresh[-1]
            if current != stable_src:
                stable_src = current
                stable_since = time.monotonic()
            elif stable_since and time.monotonic() - stable_since >= 4:
                raw = _read_url_bytes(page, current)
                _write_png_exclusive(output, raw)
                return current, page.url
        else:
            stable_src = None
            stable_since = None
        time.sleep(2)
    raise BrowserTaskError(f"timed out waiting for fresh session-scoped image: {output.name}")


def execute(spec_path: Path, timeout: int, model_effort: str, require_model: str) -> dict[str, Any]:
    spec, shared, candidate_root = _load_task(spec_path)
    if os.environ.get(APPROVAL_ENV) != spec["shared_contract_sha256"]:
        raise BrowserTaskError(f"live execution requires {APPROVAL_ENV}=<shared_contract_sha256>")
    if not BROWSER_ADAPTER_PATH.is_file():
        raise BrowserTaskError(f"browser adapter browser surface missing: {BROWSER_ADAPTER_PATH}")
    browser_adapter = _load_module("heituz_browser_adapter_review_surface", BROWSER_ADAPTER_PATH)
    sources = _input_inventory(shared)
    ledger_path = candidate_root / "task-ledger.json"
    ledger = core.read_json(ledger_path) if ledger_path.exists() else {
        "schema_version": 1,
        "task_id": spec["task_id"],
        "candidate_set": spec["candidate_set"],
        "shared_contract_sha256": spec["shared_contract_sha256"],
        "outputs": {},
    }
    if ledger.get("shared_contract_sha256") != spec["shared_contract_sha256"]:
        raise BrowserTaskError("candidate ledger belongs to a different shared contract")

    for output_spec in shared["outputs"]:
        output = candidate_root / output_spec["filename"]
        row = ledger["outputs"].get(output_spec["id"])
        if _verified_resume(output, row):
            continue
        if output.exists():
            raise BrowserTaskError(f"unowned or tampered output blocks resume: {output}")

    lock = candidate_root / ".browser-task.lock"
    try:
        lock_fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise BrowserTaskError(f"candidate set already has an active executor: {lock}") from exc
    os.close(lock_fd)

    package_path = Path(spec["shared_contract_path"]).resolve()
    session_url = None
    completed_now = []
    try:
        if not browser_adapter.ensure_browser(None):
            raise BrowserTaskError("browser adapter CDP browser unavailable; no fallback allowed")
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            browser = pw.chromium.connect_over_cdp(browser_adapter.CDP_URL)
            ctx = browser_adapter.pick_context(browser)
            if ctx is None:
                raise BrowserTaskError("no authenticated browser adapter browser context")
            page = ctx.new_page()
            browser_adapter._guard_dialogs(ctx, page)
            page.goto(browser_adapter.CHATGPT_URL, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(2500)
            if not browser_adapter.looks_logged_in(page):
                raise BrowserTaskError("ChatGPT login not verified")
            verified, observed_model = browser_adapter.select_model(page, model_effort, require_model=require_model)
            if not verified:
                raise BrowserTaskError("required browser GPT model/effort not verified; no provider fallback")

            pending = [o for o in shared["outputs"] if not _verified_resume(candidate_root / o["filename"], ledger["outputs"].get(o["id"]))]
            if pending:
                _attach_all_once(page, [*sources, package_path])
            for index, output_spec in enumerate(pending):
                output = candidate_root / output_spec["filename"]
                if index == 0:
                    prefix = (
                        "The attached JSON is the immutable folder contract and the attached images are the complete original folder. "
                        "Use every source only according to its Vision role map. Complete this entire output inventory in this one chat; "
                        "never use generated results as inputs. Now generate exactly this output as one downloadable image: "
                    )
                else:
                    prefix = (
                        "Continue the same complete-folder run using only the original images and immutable contract already attached; "
                        "do not use any generated result as an input. Generate exactly this next output as one downloadable image: "
                    )
                prompt = f"{prefix}{output_spec['id']} / {output_spec['filename']}. {output_spec['prompt']}"
                source_url, session_url = _send_and_recover(page, browser_adapter, prompt, output, timeout)
                row = {
                    "state": "completed",
                    "filename": output_spec["filename"],
                    "sha256": core.sha256_file(output),
                    "size": output.stat().st_size,
                    "session_url": session_url,
                    "source_dom_url_sha256": core.sha256_bytes(source_url.encode("utf-8")),
                    "observed_browser_model": observed_model,
                    "all_sources_uploaded_in_initial_turn": True,
                    "generated_result_chaining": False,
                }
                ledger["outputs"][output_spec["id"]] = row
                ledger["session_url"] = session_url
                _atomic_json(ledger_path, ledger)
                completed_now.append(output_spec["id"])
            page.close()

        complete = all(_verified_resume(candidate_root / o["filename"], ledger["outputs"].get(o["id"])) for o in shared["outputs"])
        if not complete:
            raise BrowserTaskError("task ended without a hash-verified complete folder set")
        ledger["state"] = "complete"
        ledger["identical_output_inventory"] = [o["filename"] for o in shared["outputs"]]
        _atomic_json(ledger_path, ledger)
        return {
            "live": True,
            "task_id": spec["task_id"],
            "candidate_set": spec["candidate_set"],
            "state": "complete",
            "completed_now": completed_now,
            "resumed_count": len(shared["outputs"]) - len(completed_now),
            "ledger": str(ledger_path),
            "session_url": session_url or ledger.get("session_url"),
        }
    finally:
        lock.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-spec", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--model-effort", default="pro")
    parser.add_argument("--require-model", default="GPT-5.5")
    args = parser.parse_args()
    try:
        result = execute(args.task_spec.resolve(), args.timeout, args.model_effort, args.require_model) if args.execute else dry_run(args.task_spec.resolve())
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except (BrowserTaskError, core.ContractError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
