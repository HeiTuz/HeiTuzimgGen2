"""Cross-platform resolution for the official Codex CLI.

Resolution is deliberately read-only. It never installs or replaces Codex while a
transport command is running; installation is handled by ``install_codex_cli.py``.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Callable, Mapping, Sequence

CODEX_OVERRIDE_ENV = "HEITUZ_IMGGEN2_CODEX_BIN"
CODEX_INSTALL_DIR_ENV = "CODEX_INSTALL_DIR"
OFFICIAL_INSTALLER_URL = "https://chatgpt.com/codex/install.sh"
Version = tuple[int, int, int]


class CodexResolutionError(RuntimeError):
    """The configured or discovered Codex CLI cannot be used safely."""


@dataclass(frozen=True)
class ResolvedCodex:
    command: str
    source: str
    version: Version
    @property
    def path(self) -> str:
        return self.command

    @property
    def provenance(self) -> dict[str, object]:
        return {
            "path": self.command,
            "source": self.source,
            "version": list(self.version),
        }


def canonical_codex_path(
    *, platform: str | None = None, home: Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> Path | None:
    """Return the official standalone Codex executable location for a platform."""
    platform = sys.platform if platform is None else platform
    environ = os.environ if environ is None else environ
    if platform.startswith(("darwin", "linux")):
        return (Path.home() if home is None else home) / ".local" / "bin" / "codex"
    if platform.startswith("win"):
        local_app_data = environ.get("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data) / "Programs" / "OpenAI" / "Codex" / "bin" / "codex.exe"
    return None


def parse_codex_version(output: str) -> Version | None:
    """Extract a stable semantic version from ``codex --version`` output."""
    match = re.search(r"\b(?:codex(?:-cli)?\s+)?v?(\d+)\.(\d+)\.(\d+)\b", output, re.IGNORECASE)
    if match is None:
        return None
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def _is_executable(path: Path, platform: str) -> bool:
    if not path.is_file():
        return False
    if platform.startswith("win"):
        return path.suffix.lower() in {".exe", ".cmd"}
    return os.access(path, os.X_OK)


def probe_codex_version(
    command: str,
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> Version:
    """Run the harmless version command and reject unavailable or malformed CLIs."""
    try:
        completed = runner(
            [command, "--version"],
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise CodexResolutionError("Codex version probe could not run.") from exc
    if completed.returncode != 0:
        raise CodexResolutionError("Codex version probe failed.")
    version = parse_codex_version(f"{completed.stdout}\n{completed.stderr}")
    if version is None:
        raise CodexResolutionError("Codex version probe returned an unrecognized version.")
    return version


def _validated_candidate(
    command: str,
    source: str,
    *,
    platform: str,
    minimum_version: Version | None,
    runner: Callable[..., subprocess.CompletedProcess[str]],
) -> ResolvedCodex:
    path = Path(command).expanduser().resolve(strict=False)
    if not _is_executable(path, platform):
        raise CodexResolutionError("Codex executable is missing or not executable.")
    version = probe_codex_version(str(path), runner=runner)
    if minimum_version is not None and version < minimum_version:
        formatted = ".".join(str(part) for part in minimum_version)
        raise CodexResolutionError(f"Codex version is below the resolver compatibility floor ({formatted}).")
    return ResolvedCodex(command=str(path), source=source, version=version)


def resolve_codex_command(
    explicit: str | Path | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    platform: str | None = None,
    home: Path | None = None,
    minimum_version: Version | None = None,
    which: Callable[[str], str | None] = shutil.which,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> ResolvedCodex:
    """Resolve Codex by explicit override, environment, install dir, standard path, then PATH.

    A compatibility floor is opt-in because no permanent minimum version is
    established by the public Codex documentation. Malformed or non-running
    version probes are always rejected.
    """
    platform = sys.platform if platform is None else platform
    environ = os.environ if environ is None else environ
    windows = platform.startswith("win")
    executable_name = "codex.exe" if windows else "codex"
    canonical = canonical_codex_path(platform=platform, home=home, environ=environ)
    candidates: list[tuple[str, str, bool]] = []
    if explicit is not None:
        candidates.append(("explicit", str(explicit), True))
    elif environ.get(CODEX_OVERRIDE_ENV):
        candidates.append(("environment", environ[CODEX_OVERRIDE_ENV], True))
    else:
        install_dir = environ.get(CODEX_INSTALL_DIR_ENV)
        if install_dir:
            candidates.append(("install_dir", str(Path(install_dir).expanduser() / executable_name), False))
        if canonical is not None:
            candidates.append(("official", str(canonical), False))
        path_names = ("codex", "codex.exe", "codex.cmd") if windows else ("codex",)
        for path_name in path_names:
            path_candidate = which(path_name)
            if path_candidate:
                candidates.append(("path", path_candidate, False))
                break

    failures: list[str] = []
    seen: set[str] = set()
    for source, command, required in candidates:
        normalized = str(Path(command).expanduser())
        if normalized in seen:
            continue
        seen.add(normalized)
        try:
            return _validated_candidate(
                command,
                source,
                platform=platform,
                minimum_version=minimum_version,
                runner=runner,
            )
        except CodexResolutionError as exc:
            if required:
                raise CodexResolutionError(f"Configured {source} Codex command is unusable: {exc}") from None
            failures.append(str(exc))

    detail = failures[-1] if failures else "Codex was not found."
    raise CodexResolutionError(f"Official Codex CLI is unavailable: {detail}")


def canonical_install_required(
    *,
    platform: str | None = None,
    home: Path | None = None,
    minimum_version: Version | None = None,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> bool:
    """Whether the official macOS/Linux installer must restore canonical Codex."""
    platform = sys.platform if platform is None else platform
    if not platform.startswith(("darwin", "linux")):
        return False
    canonical = canonical_codex_path(platform=platform, home=home)
    if canonical is None:
        return False
    try:
        _validated_candidate(
            str(canonical),
            "official",
            platform=platform,
            minimum_version=minimum_version,
            runner=runner,
        )
    except CodexResolutionError:
        return True
    return False


def official_installer_command() -> Sequence[str]:
    """Return the documented macOS/Linux standalone installer command."""
    return ("sh", "-c", f"curl -fsSL {OFFICIAL_INSTALLER_URL} | sh")
