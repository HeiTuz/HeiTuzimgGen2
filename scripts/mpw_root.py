"""Resolve the local HeiTuzMPW installation used by cross-skill tests.

``HEITUZ_MPW_ROOT`` takes precedence when it is present in the environment and
must name a valid installation; an invalid override is an error. Without an
override, Hermes, Claude, then Codex standard locations are checked in that
order. A valid installation contains a ``SKILL.md`` declaring
``name: HeiTuzMPW``. ``None`` means no installation was found; callers that
need contract authority must additionally require its manifest.
"""

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


def is_mpw_installation(root: Path) -> bool:
    """Return whether root has the minimal HeiTuzMPW installation identity."""
    skill = root / "SKILL.md"
    if not root.is_dir() or not skill.is_file():
        return False
    try:
        return "name: HeiTuzMPW" in skill.read_text(encoding="utf-8")
    except OSError:
        return False


def validate_mpw_root(root: Path, *, source: str) -> Path:
    """Return root when it is a HeiTuzMPW installation, otherwise raise."""
    candidate = root.expanduser()
    if not is_mpw_installation(candidate):
        raise RuntimeError(
            f"{source} is set but is not an existing HeiTuzMPW installation: {candidate}"
        )
    return candidate


def resolve_mpw_root() -> Path | None:
    """Return the validated override or first validated standard installation."""
    if "HEITUZ_MPW_ROOT" in os.environ:
        override = os.environ["HEITUZ_MPW_ROOT"]
        if not override.strip():
            raise RuntimeError("HEITUZ_MPW_ROOT is set but is blank.")
        return validate_mpw_root(Path(override), source="HEITUZ_MPW_ROOT")

    for candidate in STANDARD_ROOTS:
        root = candidate.expanduser()
        if is_mpw_installation(root):
            return root
    return None


def require_contracts_manifest(root: Path) -> Path:
    """Return the contracts manifest or fail because the installation is incomplete."""
    manifest = root / "contracts" / "manifest.json"
    if not manifest.is_file():
        raise RuntimeError(
            f"incomplete HeiTuzMPW installation: contracts manifest not found: {manifest}"
        )
    return manifest