#!/usr/bin/env python3
"""Locate HeiTuzMPW and compile simple or bulk image prompts without residue."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Literal

MpwMode = Literal["auto", "off", "required"]


class MpwPromptError(RuntimeError):
    pass


def discover_mpw_root(explicit: Path | None = None) -> Path | None:
    candidates: list[Path] = []
    if explicit is not None:
        candidates.append(explicit)
    env_root = os.environ.get("HEITUZ_MPW_ROOT")
    if env_root:
        candidates.append(Path(env_root))
    here = Path(__file__).resolve().parent.parent
    candidates.extend((
        Path.home() / ".hermes" / "skills" / "prompt-writing" / "HeiTuzMPW",
        Path.home() / ".hermes" / "skills" / "HeiTuzMPW",
        Path.home() / ".codex" / "skills" / "HeiTuzMPW",
        here.parent / "HeiTuzMPW-release",
        here.parent / "HeiTuzMPW",
    ))
    seen: set[Path] = set()
    for candidate in candidates:
        root = candidate.expanduser().resolve(strict=False)
        if root in seen:
            continue
        seen.add(root)
        if (root / "scripts" / "compile_image_variations.py").is_file():
            return root
    return None


def compile_manifest(
    prompt: str,
    style: str,
    count: int,
    output: Path,
    *,
    mpw_root: Path | None = None,
    seed: int | None = None,
    output_prefix: str = "images",
) -> Path:
    root = discover_mpw_root(mpw_root)
    if root is None:
        raise MpwPromptError("HeiTuzMPW variation compiler is unavailable; install/update HeiTuzMPW or pass --mpw-root.")
    compiler = root / "scripts" / "compile_image_variations.py"
    output.parent.mkdir(parents=True, exist_ok=True)
    request = {"concept": prompt, "style": style, "output_prefix": output_prefix, "locks": {}}
    request_path = output.with_suffix(".request.json")
    request_path.write_text(json.dumps(request, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    command = [sys.executable, str(compiler), "--request", str(request_path), "--count", str(count), "--output", str(output)]
    if seed is not None:
        command.extend(("--seed", str(seed)))
    completed = subprocess.run(command, text=True, capture_output=True, check=False)
    request_path.unlink(missing_ok=True)
    if completed.returncode != 0:
        output.unlink(missing_ok=True)
        detail = completed.stderr.strip() or "compiler failed without diagnostics"
        raise MpwPromptError(f"HeiTuzMPW variation compiler failed: {detail}")
    return output


def compile_single_prompt(prompt: str, *, mode: MpwMode = "auto", mpw_root: Path | None = None) -> tuple[str, bool]:
    if mode == "off":
        return prompt, False
    root = discover_mpw_root(mpw_root)
    if root is None:
        if mode == "required":
            raise MpwPromptError("--mpw required but HeiTuzMPW variation compiler was not found.")
        return prompt, False
    with tempfile.TemporaryDirectory(prefix="heituz-mpw-single-") as tmp:
        manifest = Path(tmp) / "single.jsonl"
        compile_manifest(prompt, "", 1, manifest, mpw_root=root, output_prefix="images")
        try:
            row = json.loads(manifest.read_text(encoding="utf-8").splitlines()[0])
            compiled = row["full_prompt"]
        except (IndexError, KeyError, json.JSONDecodeError) as exc:
            raise MpwPromptError("HeiTuzMPW returned an invalid single-prompt manifest.") from exc
    if not isinstance(compiled, str) or not compiled.strip():
        raise MpwPromptError("HeiTuzMPW returned an empty compiled prompt.")
    return compiled.strip(), True
