"""Resolve the local HeiTuzMPW installation used by cross-skill tests."""

import os
from pathlib import Path


STANDARD_ROOTS = (
    Path("~/.hermes/skills/prompt-writing/HeiTuzMPW"),
    Path("~/.claude/skills/HeiTuzMPW"),
    Path("~/.codex/skills/HeiTuzMPW"),
)


def no_installation_message() -> str:
    return (
        "SKIP: no HeiTuzMPW installation found "
        "(checked HEITUZ_MPW_ROOT and ~/.hermes/skills/prompt-writing/HeiTuzMPW, "
        "~/.claude/skills/HeiTuzMPW, ~/.codex/skills/HeiTuzMPW)"
    )


def resolve_mpw_root() -> Path | None:
    """Return the configured or first standard HeiTuzMPW root, if installed."""
    override = os.environ.get("HEITUZ_MPW_ROOT")
    if override:
        root = Path(override).expanduser()
        if not root.is_dir():
            raise RuntimeError(
                "HEITUZ_MPW_ROOT is set but is not an existing HeiTuzMPW directory: "
                f"{root}"
            )
        return root

    for candidate in STANDARD_ROOTS:
        root = candidate.expanduser()
        if root.is_dir():
            return root
    return None
