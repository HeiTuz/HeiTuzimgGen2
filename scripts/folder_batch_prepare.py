#!/usr/bin/env python3
"""Prepare a folder of source images for the HeiTuzImgGen2 batch runner."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Sequence

from codex_subscription_batch import BatchError, load_manifest
from output_lifecycle import (
    create_job_dir,
    is_symlink_or_reparse,
    retention_hours,
    validate_persistent_destination,
)

SUPPORTED_SUFFIXES = {".jpeg", ".jpg", ".png", ".webp"}
MAX_SOURCE_FILES = 500
MAX_TOTAL_SOURCE_BYTES = 5 * 1024 * 1024 * 1024


class FolderPrepareError(RuntimeError):
    pass


def _contained(root: Path, candidate: Path) -> bool:
    try:
        candidate.relative_to(root)
        return True
    except ValueError:
        return False


def _inventory(
    input_dir: Path,
    recursive: bool,
    excluded_root: Path | None = None,
) -> tuple[list[tuple[Path, Path]], int]:
    items: list[tuple[Path, Path]] = []
    ignored_unsupported_file_count = 0
    total_bytes = 0
    pending = [input_dir]
    while pending:
        directory = pending.pop()
        try:
            entries = list(os.scandir(directory))
        except OSError as exc:
            raise FolderPrepareError(f"Unable to inventory source directory: {directory}") from exc
        for entry in entries:
            candidate = Path(entry.path)
            if is_symlink_or_reparse(candidate):
                raise FolderPrepareError(
                    f"Input tree contains a symlink, junction, or reparse point: {candidate}"
                )
            resolved = candidate.resolve(strict=False)
            if not _contained(input_dir, resolved):
                raise FolderPrepareError(
                    f"Input entry resolves outside the authorized source directory: {candidate}"
                )
            if excluded_root is not None and _contained(excluded_root, resolved):
                continue
            try:
                is_directory = entry.is_dir(follow_symlinks=False)
                is_file = entry.is_file(follow_symlinks=False)
            except OSError as exc:
                raise FolderPrepareError(f"Unable to inspect source entry: {candidate}") from exc
            if is_directory:
                if recursive:
                    pending.append(candidate)
                continue
            if not is_file:
                continue
            if candidate.suffix.lower() not in SUPPORTED_SUFFIXES:
                ignored_unsupported_file_count += 1
                continue
            try:
                size = entry.stat(follow_symlinks=False).st_size
            except OSError as exc:
                raise FolderPrepareError(f"Unable to size source image: {candidate}") from exc
            if len(items) >= MAX_SOURCE_FILES:
                raise FolderPrepareError(
                    f"Input folder exceeds the {MAX_SOURCE_FILES}-image safety limit"
                )
            total_bytes += size
            if total_bytes > MAX_TOTAL_SOURCE_BYTES:
                raise FolderPrepareError(
                    f"Input folder exceeds the {MAX_TOTAL_SOURCE_BYTES}-byte safety limit"
                )
            relative = candidate.relative_to(input_dir)
            final_source = candidate.resolve(strict=True)
            if not _contained(input_dir, final_source):
                raise FolderPrepareError(
                    f"Input image changed to an out-of-scope path during inventory: {candidate}"
                )
            items.append((relative, final_source))
    return (
        sorted(items, key=lambda item: item[0].as_posix().casefold()),
        ignored_unsupported_file_count,
    )


def _job_ids(inventory: list[tuple[Path, Path]]) -> list[str]:
    identifiers: list[str] = []
    seen: set[str] = set()
    for index, (relative, _source) in enumerate(inventory, 1):
        readable = re.sub(
            r"[^a-z0-9._-]+",
            "-",
            relative.with_suffix("").as_posix().lower(),
        )
        readable = readable.strip("-.") or f"image-{index}"
        digest = hashlib.sha256(relative.as_posix().encode("utf-8")).hexdigest()[:16]
        preferred = f"{readable[:100]}-{digest}"
        candidate = preferred
        suffix = 2
        while candidate.casefold() in seen:
            candidate = f"{preferred[:124 - len(str(suffix))]}-{suffix}"
            suffix += 1
        seen.add(candidate.casefold())
        identifiers.append(candidate)
    return identifiers


def _output_paths(inventory: list[tuple[Path, Path]]) -> list[Path]:
    bases = [relative.with_suffix(".png") for relative, _source in inventory]
    counts: dict[str, int] = {}
    for base in bases:
        key = base.as_posix().casefold()
        counts[key] = counts.get(key, 0) + 1
    outputs: list[Path] = []
    seen: set[str] = set()
    for (relative, _source), base in zip(inventory, bases):
        preferred = base
        if counts[base.as_posix().casefold()] > 1:
            extension = relative.suffix.lower().lstrip(".") or "image"
            preferred = relative.with_name(f"{relative.stem}-{extension}.png")
        candidate = preferred
        suffix = 2
        while candidate.as_posix().casefold() in seen:
            candidate = preferred.with_name(f"{preferred.stem}-{suffix}.png")
            suffix += 1
        seen.add(candidate.as_posix().casefold())
        outputs.append(candidate)
    return outputs


def prepare_folder_batch(
    input_dir: Path,
    prompt: str,
    output_root: Path | None = None,
    *,
    recursive: bool = True,
) -> dict[str, object]:
    input_dir = input_dir.expanduser().absolute()
    if is_symlink_or_reparse(input_dir):
        raise FolderPrepareError(
            f"Input directory must not be a symlink, junction, or reparse point: {input_dir}"
        )
    input_dir = input_dir.resolve()
    if not input_dir.is_dir():
        raise FolderPrepareError(f"Input directory does not exist: {input_dir}")
    if not prompt.strip():
        raise FolderPrepareError("Prompt must not be empty.")

    resolved_output = (
        None
        if output_root is None
        else validate_persistent_destination(output_root).resolve(strict=False)
    )
    if resolved_output == input_dir:
        raise FolderPrepareError("Output directory must not be the input directory.")
    excluded_subtree = (
        resolved_output
        if resolved_output is not None and _contained(input_dir, resolved_output)
        else None
    )
    inventory, ignored_unsupported_file_count = _inventory(
        input_dir,
        recursive,
        excluded_subtree,
    )
    if not inventory:
        raise FolderPrepareError(f"No supported images found in: {input_dir}")

    temporary_outputs = output_root is None
    if temporary_outputs:
        job_root = create_job_dir("folder")
        resolved_output = job_root / "outputs"
        manifest = job_root / "jobs.jsonl"
    else:
        assert resolved_output is not None
        manifest_dir = resolved_output / ".heituzimggen2-manifests"
        manifest_dir.mkdir(parents=True, exist_ok=True)
        descriptor, manifest_name = tempfile.mkstemp(
            prefix="jobs-", suffix=".jsonl", dir=manifest_dir
        )
        os.close(descriptor)
        manifest = Path(manifest_name)
    assert resolved_output is not None
    resolved_output.mkdir(parents=True, exist_ok=True)

    records = []
    output_paths = _output_paths(inventory)
    job_ids = _job_ids(inventory)
    for (relative, source), output_path, job_id in zip(
        inventory,
        output_paths,
        job_ids,
    ):
        records.append(
            {
                "id": job_id,
                "prompt": prompt.strip(),
                "output_path": output_path.as_posix(),
                "images": [str(source)],
                "promotional": False,
                "rendered_text_exists": False,
            }
        )
    manifest.write_text(
        "\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n",
        encoding="utf-8",
    )
    load_manifest(manifest, resolved_output)
    return {
        "input_dir": str(input_dir),
        "manifest": str(manifest.resolve()),
        "output_root": str(resolved_output.resolve()),
        "source_count": len(records),
        "ignored_unsupported_file_count": ignored_unsupported_file_count,
        "temporary_outputs": temporary_outputs,
        "temporary_manifest": temporary_outputs,
        "retention_hours": retention_hours() if temporary_outputs else None,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", required=True, type=Path)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--no-recursive", action="store_true")
    args = parser.parse_args(argv)
    try:
        summary = prepare_folder_batch(
            args.input_dir,
            args.prompt,
            args.output_root,
            recursive=not args.no_recursive,
        )
    except (FolderPrepareError, BatchError, ValueError, OSError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=__import__("sys").stderr)
        return 2
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
