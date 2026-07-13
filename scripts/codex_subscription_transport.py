#!/usr/bin/env python3
"""Fail-closed transport for Codex CLI subscription image generation.

This module never reads auth files or calls private/API-key endpoints. Live execution
requires an explicit flag and approval environment marker; dry-run is the default.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
import shutil
import re
import subprocess
import sys
from typing import Sequence

GENERATED_IMAGES_DIR = Path.home() / ".codex" / "generated_images"
DOWNLOADS_DIR = Path.home() / "Downloads"
REASONING_EFFORT = "medium"
APPROVAL_ENV = "HERMES_IMAGE_LIVE_APPROVED"
CLI_TIMEOUT_SECONDS = 900
_SESSION_ID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


def _slug(prompt: str, limit: int = 40) -> str:
    slug = "-".join(re.findall(r"[a-z0-9]+", prompt.lower()))[:limit].strip("-")
    return slug or "image"


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%dT%H%M%S")


def _dedupe(path: Path) -> Path:
    if not path.exists():
        return path
    for index in range(2, 1000):
        candidate = path.with_name(f"{path.stem}-{index}{path.suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"Too many output collisions for {path}")


def resolve_output(prompt: str, output: Path | None, batch_dir: Path | None) -> Path:
    """Single generation defaults to ~/Downloads; batch work uses a dated subfolder.

    An explicit --output always wins. --output and --batch-dir are mutually exclusive
    (enforced by the caller). Directories are created so validation can proceed.
    """
    if output is not None:
        return output.expanduser()
    filename = f"{_slug(prompt)}-{_timestamp()}.png"
    if batch_dir is not None:
        base = batch_dir.expanduser() / datetime.now().strftime("%Y%m%d")
    else:
        base = DOWNLOADS_DIR
    base.mkdir(parents=True, exist_ok=True)
    return _dedupe(base / filename)


class TransportError(RuntimeError):
    pass


def build_command(prompt: str, output: Path, images: Sequence[Path]) -> list[str]:
    codex = shutil.which("codex")
    if not codex:
        raise TransportError("Official Codex CLI is not installed or not on PATH.")
    instruction = (
        "Use Codex's built-in imagegen skill to create or edit exactly one image. "
        "If reference images are attached, use them as the basis for the edit or combination. "
        "Let Codex select the supported image model and leave the generated PNG in "
        "~/.codex/generated_images/<session_id>/. "
        "Do not use HTTP clients, API keys, browser/DOM automation, private APIs, "
        "or any fallback provider. "
        f"User image request: {prompt}"
    )
    command = [
        codex,
        "exec",
        "--skip-git-repo-check",
        "--ephemeral",
        "--json",
        "--config",
        f'model_reasoning_effort="{REASONING_EFFORT}"',
        "--sandbox",
        "workspace-write",
        "--cd",
        str(output.parent),
    ]
    for image in images:
        command.extend(("--image", str(image)))
    command.append(instruction)
    return command


def validate_request(prompt: str, output: Path, images: Sequence[Path]) -> None:
    if not prompt.strip():
        raise TransportError("Prompt must not be empty.")
    if output.suffix.lower() != ".png":
        raise TransportError("Output must use .png because the Codex imagegen artifact is a PNG.")
    if output.exists():
        raise TransportError(f"Refusing to overwrite existing output: {output}")
    if not output.parent.is_dir():
        raise TransportError(f"Output directory does not exist: {output.parent}")
    if len(images) > 4:
        raise TransportError("At most four reference images are supported.")
    for image in images:
        if not image.is_file():
            raise TransportError(f"Reference image is not a file: {image}")


def request_summary(command: Sequence[str], output: Path, images: Sequence[Path]) -> dict[str, object]:
    return {
        "transport": "official-codex-cli-subscription",
        "requested_model": None,
        "observed_model": None,
        "reasoning_effort": REASONING_EFFORT,
        "output": str(output),
        "reference_count": len(images),
        "command": ["<prompt>" if item.startswith("User image request:") else item for item in command[:-1]] + ["<image-instruction>"],
        "live": False,
        "model_identity_attested": False,
    }


def generated_pngs(root: Path | None = None) -> set[Path]:
    root = GENERATED_IMAGES_DIR if root is None else root
    if not root.is_dir():
        return set()
    return {path.resolve() for path in root.rglob("*.png") if path.is_file()}


def session_pngs(cli_output: str, root: Path | None = None) -> set[Path]:
    """PNGs under session dirs whose ids appear in the CLI output.

    Scoping to the session id avoids picking up artifacts from a concurrent
    Codex session. Returns an empty set when no session dir matches.
    """
    root = GENERATED_IMAGES_DIR if root is None else root
    found: set[Path] = set()
    for session_id in set(_SESSION_ID_RE.findall(cli_output or "")):
        session_dir = root / session_id
        if session_dir.is_dir():
            found.update(p.resolve() for p in session_dir.rglob("*.png") if p.is_file())
    return found

def classify_cli_failure(stdout: str, stderr: str) -> str:
    """Return a secret-free error category without retaining subprocess output."""
    text = f"{stdout}\n{stderr}".lower()
    rules = (
        ("model_unavailable", r"model.{0,80}(not found|unknown|unsupported|unavailable|does not exist|invalid)"),
        ("authentication_required", r"(not logged in|login required|authentication required|unauthorized|invalid authentication)"),
        ("entitlement_denied", r"(not entitled|entitlement|does not have access|permission denied|forbidden)"),
        ("rate_limited", r"(rate limit|too many requests|usage limit|quota exceeded)"),
        ("image_tool_unavailable", r"(image_generation|image generation).{0,80}(unavailable|unsupported|disabled|not enabled|not found)"),
    )
    for category, pattern in rules:
        if re.search(pattern, text):
            return category
    return "unknown_cli_failure"



def run(prompt: str, output: Path, images: Sequence[Path], execute: bool = False) -> dict[str, object]:
    output = output.expanduser().resolve()
    refs = [image.expanduser().resolve() for image in images]
    validate_request(prompt, output, refs)
    command = build_command(prompt, output, refs)
    summary = request_summary(command, output, refs)
    if not execute:
        return summary
    if os.environ.get(APPROVAL_ENV) != "1":
        raise TransportError(
            f"Live generation is blocked. Obtain approval immediately before the call, then set {APPROVAL_ENV}=1 for that invocation."
        )
    before = generated_pngs()
    try:
        completed = subprocess.run(
            command,
            cwd=output.parent,
            text=True,
            capture_output=True,
            timeout=CLI_TIMEOUT_SECONDS,
            check=False,
            env=os.environ.copy(),
        )
    except subprocess.TimeoutExpired:
        raise TransportError(
            f"Codex CLI timed out after {CLI_TIMEOUT_SECONDS}s; no output retained."
        ) from None
    cli_output = f"{completed.stdout}\n{completed.stderr}"
    candidates = session_pngs(cli_output) - before
    if not candidates:
        candidates = generated_pngs() - before
    fresh = {path for path in candidates if path.stat().st_size > 0}
    generated = max(fresh, key=lambda path: path.stat().st_mtime_ns) if fresh else None
    if generated is None:
        if completed.returncode != 0:
            category = classify_cli_failure(completed.stdout, completed.stderr)
            raise TransportError(
                f"Codex CLI failed with exit code {completed.returncode}; category={category}; "
                "no new PNG was found; raw output withheld to protect secrets."
            )
        raise TransportError("Codex CLI completed but did not produce a new PNG under ~/.codex/generated_images.")
    shutil.copy2(generated, output)
    summary.update(
        {
            "live": True,
            "bytes": output.stat().st_size,
            "source_artifact": str(generated),
            "cli_exit_code": completed.returncode,
            "warning": (
                "Codex returned nonzero after creating the PNG; the artifact was verified externally."
                if completed.returncode != 0
                else None
            ),
        }
    )
    return summary


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--output", type=Path, help="Explicit output path; wins over defaults")
    parser.add_argument("--batch-dir", type=Path, help="Folder-based batch root; outputs go to a dated subfolder inside it")
    parser.add_argument("--image", action="append", default=[], type=Path)
    parser.add_argument("--execute", action="store_true", help="Perform the approved live call")
    args = parser.parse_args(argv)
    if args.output is not None and args.batch_dir is not None:
        print(json.dumps({"error": "Use either --output or --batch-dir, not both."}), file=sys.stderr)
        return 2
    try:
        output = resolve_output(args.prompt, args.output, args.batch_dir)
        print(json.dumps(run(args.prompt, output, args.image, args.execute), indent=2))
    except TransportError as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
