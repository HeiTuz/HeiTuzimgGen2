#!/usr/bin/env python3
"""Install the official standalone Codex CLI only when canonical repair is needed."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from typing import Sequence

from codex_cli_resolver import (
    CodexResolutionError,
    canonical_install_required,
    canonical_codex_path,
    official_installer_command,
    resolve_codex_command,
)


def plan(*, platform: str | None = None) -> dict[str, object]:
    canonical = canonical_codex_path(platform=platform)
    if canonical is None:
        return {
            "action": "manual_install_required",
            "reason": "The official standalone installer is supported only on macOS and Linux.",
        }
    if not canonical_install_required(platform=platform):
        resolved = resolve_codex_command(canonical, platform=platform)
        return {
            "action": "already_canonical",
            "command": resolved.command,
            "version": ".".join(str(part) for part in resolved.version),
        }
    return {
        "action": "install_canonical",
        "canonical_command": str(canonical),
        "installer_command": list(official_installer_command()),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Print the non-mutating install decision")
    args = parser.parse_args(argv)
    decision = plan()
    if args.dry_run or decision["action"] != "install_canonical":
        print(json.dumps(decision, indent=2))
        return 0
    completed = subprocess.run(decision["installer_command"], check=False)
    if completed.returncode != 0:
        print(json.dumps({"error": "Official Codex installer failed."}), file=sys.stderr)
        return completed.returncode or 1
    try:
        resolved = resolve_codex_command(canonical_codex_path())
    except CodexResolutionError as exc:
        print(json.dumps({"error": f"Official Codex installer completed but canonical Codex is unavailable: {exc}"}), file=sys.stderr)
        return 1
    print(json.dumps({"action": "installed_canonical", "command": resolved.command, "version": ".".join(map(str, resolved.version))}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
