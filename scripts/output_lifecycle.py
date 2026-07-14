#!/usr/bin/env python3
"""Safe temporary workspace lifecycle for HeiTuzImgGen2 artifacts."""

from __future__ import annotations

import contextlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import tempfile
import time
import uuid

try:
    import fcntl  # POSIX
except ImportError:  # pragma: no cover - exercised on Windows
    fcntl = None
    import msvcrt

RETENTION_HOURS_ENV = "HEITUZ_IMAGE_TEMP_RETENTION_HOURS"
DEFAULT_TEMP_DIRNAME = "HeiTuzImgGen2-managed-v1"
DEFAULT_RETENTION_HOURS = 24.0
CLEANUP_CLAIM_STALE_SECONDS = 300.0
ROOT_MARKER_NAME = ".heituzimggen2-root.json"
JOB_MARKER_NAME = ".heituzimggen2-job.json"
ACTIVE_MARKER_PREFIX = ".heituzimggen2-active-"
CLEANUP_MARKER_NAME = ".heituzimggen2-cleanup"
ROOT_CLEANUP_LOCK_NAME = ".heituzimggen2-cleanup.lock"
DELETING_PREFIX = ".heituzimggen2-deleting-"
APPLICATION_NAME = "HeiTuzImgGen2"
MARKER_SCHEMA = 1
ALLOWED_JOB_KINDS = {"single", "folder"}


def _is_symlink_or_reparse(path: Path) -> bool:
    info = os.lstat(path)
    if stat.S_ISLNK(info.st_mode):
        return True
    attributes = getattr(info, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(attributes & reparse_flag)


def _write_json_exclusive(path: Path, payload: dict[str, object]) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, sort_keys=True)
            handle.write("\n")
    except Exception:
        path.unlink(missing_ok=True)
        raise


def _read_marker(
    path: Path,
    *,
    role: str,
    expected_kind: str | None = None,
) -> dict[str, object]:
    if _is_symlink_or_reparse(path) or not path.is_file():
        raise ValueError(f"Unsafe marker path: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Invalid lifecycle marker: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"Invalid lifecycle marker: {path}")
    if payload.get("application") != APPLICATION_NAME:
        raise ValueError(f"Invalid lifecycle marker: {path}")
    schema = payload.get("schema")
    if type(schema) is not int or schema != MARKER_SCHEMA:
        raise ValueError(f"Invalid lifecycle marker schema: {path}")

    fields_by_role = {
        "root": {"application", "schema"},
        "job": {"application", "schema", "kind", "job_id", "created_at"},
        "cleanup": {
            "application",
            "schema",
            "claimed_at",
            "job_id",
            "claim_id",
        },
    }
    expected_fields = fields_by_role.get(role)
    if expected_fields is None or set(payload) != expected_fields:
        raise ValueError(f"Invalid {role} lifecycle marker fields: {path}")
    if role == "job":
        kind = payload.get("kind")
        job_id = payload.get("job_id")
        created_at = payload.get("created_at")
        if (
            not isinstance(kind, str)
            or kind not in ALLOWED_JOB_KINDS
            or not isinstance(job_id, str)
            or not job_id
            or isinstance(created_at, bool)
            or not isinstance(created_at, (int, float))
            or not math.isfinite(float(created_at))
            or float(created_at) <= 0
        ):
            raise ValueError(f"Invalid job lifecycle marker values: {path}")
        if expected_kind is not None and kind != expected_kind:
            raise ValueError(f"Job marker kind mismatch: {path}")
    elif role == "cleanup":
        claimed_at = payload.get("claimed_at")
        cleanup_job_id = payload.get("job_id")
        claim_id = payload.get("claim_id")
        if (
            isinstance(claimed_at, bool)
            or not isinstance(claimed_at, (int, float))
            or not math.isfinite(float(claimed_at))
            or float(claimed_at) <= 0
            or not isinstance(cleanup_job_id, str)
            or not any(
                cleanup_job_id.startswith(f"{kind}-") for kind in ALLOWED_JOB_KINDS
            )
            or not isinstance(claim_id, str)
            or re.fullmatch(r"[0-9a-f]{32}", claim_id) is None
        ):
            raise ValueError(f"Invalid cleanup lifecycle marker values: {path}")
    return payload


def managed_root_path() -> Path:
    base = Path(tempfile.gettempdir()).expanduser().resolve()
    return base / DEFAULT_TEMP_DIRNAME


def _open_windows_directory_guard(path: Path):
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("Kernel32.dll", use_last_error=True)
    kernel32.CreateFileW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    kernel32.CreateFileW.restype = wintypes.HANDLE
    kernel32.GetFileAttributesW.argtypes = [wintypes.LPCWSTR]
    kernel32.GetFileAttributesW.restype = wintypes.DWORD
    handle = kernel32.CreateFileW(
        str(path),
        0x80 | 0x10000,  # FILE_READ_ATTRIBUTES | DELETE
        0x1 | 0x2,  # FILE_SHARE_READ | FILE_SHARE_WRITE; deliberately no DELETE
        None,
        3,  # OPEN_EXISTING
        0x02000000 | 0x00200000,  # BACKUP_SEMANTICS | OPEN_REPARSE_POINT
        None,
    )
    invalid = ctypes.c_void_p(-1).value
    if handle == invalid:
        raise ValueError(
            f"Unable to lock approved output directory against replacement: {path}: "
            f"winerror={ctypes.get_last_error()}"
        )
    attributes = kernel32.GetFileAttributesW(str(path))
    if attributes == 0xFFFFFFFF or attributes & 0x400:
        kernel32.CloseHandle(handle)
        raise ValueError(f"Approved output path became a reparse point: {path}")
    return kernel32, handle


@contextlib.contextmanager
def protected_directory_tree(root: Path, parents: Sequence[Path]):
    """Hold Windows directory handles without delete sharing for an approved path tree."""
    root = root.expanduser().absolute()
    root.mkdir(parents=True, exist_ok=True)
    if os.name != "nt":
        if _is_symlink_or_reparse(root):
            raise ValueError(f"Approved output root must not be a symlink: {root}")
        yield root
        return

    handles: list[tuple[object, object]] = []
    opened: set[str] = set()
    try:
        for candidate in [root] + sorted(
            {parent.expanduser().absolute() for parent in parents},
            key=lambda item: len(item.parts),
        ):
            try:
                relative = candidate.relative_to(root)
            except ValueError as exc:
                raise ValueError(f"Approved output parent escapes its root: {candidate}") from exc
            current = root
            components = [Path()] if not relative.parts else [Path(*relative.parts[:index]) for index in range(1, len(relative.parts) + 1)]
            for component in components:
                path = root if component == Path() else root / component
                key = os.path.normcase(str(path))
                if key in opened:
                    continue
                if path == root:
                    # Windows cannot atomically replace root-level ledger/summary
                    # files while this directory itself is held without DELETE share.
                    # The batch lock file remains the root-level live ownership guard;
                    # lock only child output directories against reparse replacement.
                    if _is_symlink_or_reparse(path):
                        raise ValueError(f"Approved output root became a reparse point: {path}")
                    opened.add(key)
                    continue
                path.mkdir(exist_ok=True)
                kernel32, handle = _open_windows_directory_guard(path)
                handles.append((kernel32, handle))
                opened.add(key)
        yield root
    finally:
        for kernel32, handle in reversed(handles):
            kernel32.CloseHandle(handle)


def is_symlink_or_reparse(path: Path) -> bool:
    """Return True for POSIX symlinks and Windows junction/reparse points."""
    return _is_symlink_or_reparse(path)


def _current_windows_sid(path: Path) -> str:
    identity_result = subprocess.run(
        ["whoami", "/user", "/fo", "csv", "/nh"],
        capture_output=True,
    )
    match = re.search(rb"S-\d-(?:\d+-)*\d+", identity_result.stdout)
    if identity_result.returncode != 0 or match is None:
        raise ValueError(f"Unable to determine the current Windows identity for: {path}")
    return match.group(0).decode("ascii")


def _windows_owner_sid(path: Path) -> str:
    if os.name != "nt":
        raise ValueError("Windows ownership inspection is unavailable on this platform")
    import ctypes
    from ctypes import wintypes

    advapi32 = ctypes.WinDLL("Advapi32.dll")
    kernel32 = ctypes.WinDLL("Kernel32.dll")
    pointer = ctypes.POINTER(ctypes.c_void_p)
    advapi32.GetNamedSecurityInfoW.argtypes = [
        wintypes.LPWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        pointer,
        pointer,
        pointer,
        pointer,
        pointer,
    ]
    advapi32.GetNamedSecurityInfoW.restype = wintypes.DWORD
    advapi32.ConvertSidToStringSidW.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(wintypes.LPWSTR),
    ]
    advapi32.ConvertSidToStringSidW.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    owner = ctypes.c_void_p()
    descriptor = ctypes.c_void_p()
    result = advapi32.GetNamedSecurityInfoW(
        str(path),
        1,  # SE_FILE_OBJECT
        1,  # OWNER_SECURITY_INFORMATION
        ctypes.byref(owner),
        None,
        None,
        None,
        ctypes.byref(descriptor),
    )
    if result != 0 or not owner.value:
        raise ValueError(f"Unable to inspect the managed Windows temporary owner: {path}")
    sid_text = wintypes.LPWSTR()
    try:
        if not advapi32.ConvertSidToStringSidW(owner, ctypes.byref(sid_text)):
            raise ValueError(f"Unable to convert the managed Windows owner SID: {path}")
        return sid_text.value
    finally:
        if sid_text:
            kernel32.LocalFree(ctypes.cast(sid_text, ctypes.c_void_p))
        if descriptor:
            kernel32.LocalFree(descriptor)


def _verify_windows_owner(path: Path) -> None:
    expected = _current_windows_sid(path)
    actual = _windows_owner_sid(path)
    if actual.casefold() != expected.casefold():
        raise ValueError(
            f"Managed temporary directory is not owned by the current Windows user: {path}"
        )


def _secure_windows_dacl(path: Path) -> None:
    """Replace inheritance with current-user and SYSTEM full-control ACEs."""
    if os.name != "nt":
        return
    user_sid = _current_windows_sid(path)
    reset_result = subprocess.run(
        ["icacls", str(path), "/reset"],
        capture_output=True,
    )
    if reset_result.returncode != 0:
        detail_bytes = reset_result.stderr or reset_result.stdout
        detail = detail_bytes.decode(errors="replace").strip()
        raise ValueError(f"Unable to reset the managed Windows temporary ACL: {path}: {detail}")
    acl_result = subprocess.run(
        [
            "icacls",
            str(path),
            "/inheritance:r",
            "/grant:r",
            f"*{user_sid}:(OI)(CI)F",
            "/grant:r",
            "*S-1-5-18:(OI)(CI)F",
        ],
        capture_output=True,
    )
    if acl_result.returncode != 0:
        detail_bytes = acl_result.stderr or acl_result.stdout
        detail = detail_bytes.decode(errors="replace").strip()
        raise ValueError(f"Unable to secure the managed Windows temporary directory: {path}: {detail}")


def temp_root() -> Path:
    root = managed_root_path()
    created = False
    try:
        if _is_symlink_or_reparse(root):
            raise ValueError(f"Managed temporary root must not be a symlink or reparse point: {root}")
        if not root.is_dir():
            raise ValueError(f"Managed temporary root is not a directory: {root}")
    except FileNotFoundError:
        root.mkdir(mode=0o700)
        created = True

    if os.name == "nt":
        _verify_windows_owner(root)
    else:
        info = os.stat(root, follow_symlinks=False)
        if hasattr(os, "getuid") and info.st_uid != os.getuid():
            raise ValueError(f"Managed temporary root is not owned by the current user: {root}")

    if created:
        if os.name == "nt":
            _secure_windows_dacl(root)
            _verify_windows_owner(root)
        else:
            os.chmod(root, 0o700)

    marker = root / ROOT_MARKER_NAME
    if marker.exists() or marker.is_symlink():
        _read_marker(marker, role="root")
    else:
        existing = list(root.iterdir())
        if existing:
            raise ValueError(
                f"Refusing to adopt non-empty unmarked temporary root: {root}. "
                f"Remove or relocate it manually, then retry."
            )
        try:
            _write_json_exclusive(
                marker,
                {"application": APPLICATION_NAME, "schema": MARKER_SCHEMA},
            )
        except FileExistsError:
            _read_marker(marker, role="root")

    if _is_symlink_or_reparse(root):
        raise ValueError(f"Managed temporary root became a symlink or reparse point: {root}")
    if not created:
        if os.name == "nt":
            _secure_windows_dacl(root)
            _verify_windows_owner(root)
        else:
            os.chmod(root, 0o700)
    return root


def retention_hours() -> float:
    raw = os.environ.get(RETENTION_HOURS_ENV)
    if raw is None or not raw.strip():
        return DEFAULT_RETENTION_HOURS
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{RETENTION_HOURS_ENV} must be a positive finite number") from exc
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{RETENTION_HOURS_ENV} must be a positive finite number")
    return value


def create_job_dir(kind: str) -> Path:
    if kind not in ALLOWED_JOB_KINDS:
        raise ValueError(f"kind must be one of: {', '.join(sorted(ALLOWED_JOB_KINDS))}")
    root = temp_root()
    job = Path(tempfile.mkdtemp(prefix=f"{kind}-", dir=root))
    try:
        if os.name == "nt":
            _secure_windows_dacl(job)
        _write_json_exclusive(
            job / JOB_MARKER_NAME,
            {
                "application": APPLICATION_NAME,
                "schema": MARKER_SCHEMA,
                "kind": kind,
                "job_id": job.name,
                "created_at": time.time(),
            },
        )
    except Exception:
        shutil.rmtree(job, ignore_errors=True)
        raise
    return job


def _contained(root: Path, candidate: Path) -> bool:
    try:
        candidate.relative_to(root)
        return True
    except ValueError:
        return False


def validate_persistent_destination(path: Path) -> Path:
    candidate = path.expanduser().absolute()
    root = managed_root_path()
    resolved_candidate = candidate.resolve(strict=False)
    if _contained(root, candidate) or _contained(root, resolved_candidate):
        raise ValueError(
            f"Explicit persistent destinations must be outside the managed temporary root: {root}"
        )
    return candidate


def _valid_job_dir(path: Path) -> bool:
    try:
        if _is_symlink_or_reparse(path) or not path.is_dir():
            return False
        kind = next((item for item in ALLOWED_JOB_KINDS if path.name.startswith(f"{item}-")), None)
        if kind is None:
            return False
        payload = _read_marker(
            path / JOB_MARKER_NAME,
            role="job",
            expected_kind=kind,
        )
        return payload.get("job_id") == path.name
    except (FileNotFoundError, OSError, ValueError):
        return False


def _managed_job_for_path(path: Path) -> Path | None:
    root = managed_root_path()
    candidate = path.expanduser().absolute()
    resolved = candidate.resolve(strict=False)
    inside = _contained(root, candidate) or _contained(root, resolved)
    if not inside:
        return None
    root = temp_root()
    try:
        relative = candidate.relative_to(root)
    except ValueError:
        relative = resolved.relative_to(root)
    if not relative.parts:
        raise ValueError("A managed job path must be below the temporary root")
    job = root / relative.parts[0]
    if not _valid_job_dir(job):
        raise ValueError(f"Managed temporary output is not inside a valid marked job: {path}")
    return job


def _lock_file(handle, *, nonblocking: bool) -> bool:
    try:
        if fcntl is not None:
            flags = fcntl.LOCK_EX | (fcntl.LOCK_NB if nonblocking else 0)
            fcntl.flock(handle.fileno(), flags)
        else:  # pragma: no cover - exercised on Windows
            handle.seek(0)
            if handle.read(1) == b"":
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            mode = msvcrt.LK_NBLCK if nonblocking else msvcrt.LK_LOCK
            msvcrt.locking(handle.fileno(), mode, 1)
        return True
    except (BlockingIOError, OSError):
        return False


def _unlock_file(handle) -> None:
    try:
        if fcntl is not None:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        else:  # pragma: no cover - exercised on Windows
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    except OSError:
        pass


@contextlib.contextmanager
def job_activity_for_path(path: Path):
    """Protect a managed job from cleanup; persistent paths are a no-op."""
    job = _managed_job_for_path(path)
    if job is None:
        yield
        return
    cleanup_marker = job / CLEANUP_MARKER_NAME
    if cleanup_marker.exists() or cleanup_marker.is_symlink():
        raise ValueError(f"Managed temporary job is being cleaned: {job}")
    marker = job / f"{ACTIVE_MARKER_PREFIX}{os.getpid()}-{uuid.uuid4().hex}.lock"
    handle = marker.open("x+b")
    locked = False
    try:
        handle.write(json.dumps({"pid": os.getpid(), "started_at": time.time()}).encode("utf-8"))
        handle.flush()
        handle.seek(0)
        locked = _lock_file(handle, nonblocking=False)
        if not locked:
            raise OSError(f"Unable to lock managed temporary job activity: {job}")
        if cleanup_marker.exists() or cleanup_marker.is_symlink() or not _valid_job_dir(job):
            raise ValueError(f"Managed temporary job is being cleaned: {job}")
        yield
    finally:
        if locked:
            _unlock_file(handle)
        handle.close()
        marker.unlink(missing_ok=True)


def _latest_mtime(path: Path) -> float | None:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return None
    except OSError:
        return float("inf")
    latest = info.st_mtime
    try:
        if _is_symlink_or_reparse(path) or not stat.S_ISDIR(info.st_mode):
            return latest
    except OSError:
        return float("inf")
    try:
        entries = list(os.scandir(path))
    except OSError:
        return float("inf")
    for entry in entries:
        if entry.name == CLEANUP_MARKER_NAME or entry.name.startswith(ACTIVE_MARKER_PREFIX):
            continue
        child_latest = _latest_mtime(Path(entry.path))
        if child_latest is not None:
            latest = max(latest, child_latest)
    return latest


def _latest_descendant_mtime(path: Path) -> float | None:
    try:
        entries = list(os.scandir(path))
    except OSError:
        return float("inf")
    latest: float | None = None
    for entry in entries:
        if entry.name == CLEANUP_MARKER_NAME or entry.name.startswith(ACTIVE_MARKER_PREFIX):
            continue
        child_latest = _latest_mtime(Path(entry.path))
        if child_latest is not None:
            latest = child_latest if latest is None else max(latest, child_latest)
    return latest


def _has_live_activity(path: Path) -> bool:
    try:
        entries = list(os.scandir(path))
    except OSError:
        return True
    for entry in entries:
        if not entry.name.startswith(ACTIVE_MARKER_PREFIX):
            continue
        marker = Path(entry.path)
        try:
            if _is_symlink_or_reparse(marker) or not marker.is_file():
                return True
            handle = marker.open("r+b")
        except (FileNotFoundError, OSError):
            return True
        try:
            if not _lock_file(handle, nonblocking=True):
                return True
            _unlock_file(handle)
        finally:
            handle.close()
        try:
            marker.unlink()
        except FileNotFoundError:
            pass
        except OSError:
            return True
    return False


def _valid_quarantine(path: Path, cutoff: float) -> bool:
    if not path.name.startswith(DELETING_PREFIX):
        return False
    try:
        if _is_symlink_or_reparse(path) or not path.is_dir():
            return False
        job_payload = _read_marker(path / JOB_MARKER_NAME, role="job")
        cleanup_payload = _read_marker(path / CLEANUP_MARKER_NAME, role="cleanup")
        job_id = job_payload.get("job_id")
        kind = job_payload.get("kind")
        claim_id = cleanup_payload.get("claim_id")
        if (
            not isinstance(job_id, str)
            or not isinstance(kind, str)
            or not job_id.startswith(f"{kind}-")
            or cleanup_payload.get("job_id") != job_id
            or path.name != f"{DELETING_PREFIX}{claim_id}-{job_id}"
        ):
            return False
        modified = _latest_descendant_mtime(path)
        return modified is not None and modified < cutoff
    except (FileNotFoundError, OSError, ValueError):
        return False


def _remove_quarantined(root: Path, cutoff: float) -> None:
    for child in list(root.iterdir()):
        if _valid_quarantine(child, cutoff) and not _has_live_activity(child):
            shutil.rmtree(child)


def _cleanup_expired_locked(root: Path, cutoff: float, current: float) -> list[Path]:
    removed: list[Path] = []
    _remove_quarantined(root, cutoff)
    for child in sorted(root.iterdir(), key=lambda item: item.name):
        if not _valid_job_dir(child) or _has_live_activity(child):
            continue
        modified = _latest_descendant_mtime(child)
        if modified is None or modified >= cutoff:
            continue
        cleanup_marker = child / CLEANUP_MARKER_NAME
        claim_id = uuid.uuid4().hex
        claim_payload = {
            "application": APPLICATION_NAME,
            "schema": MARKER_SCHEMA,
            "claimed_at": current,
            "job_id": child.name,
            "claim_id": claim_id,
        }
        try:
            _write_json_exclusive(cleanup_marker, claim_payload)
        except FileExistsError:
            try:
                stale_payload = _read_marker(cleanup_marker, role="cleanup")
                stale_claimed_at = float(stale_payload["claimed_at"])
                if (
                    stale_payload.get("job_id") != child.name
                    or stale_claimed_at > current - CLEANUP_CLAIM_STALE_SECONDS
                ):
                    continue
                cleanup_marker.unlink()
                _write_json_exclusive(cleanup_marker, claim_payload)
            except (FileExistsError, FileNotFoundError, OSError, ValueError):
                continue
        moved: Path | None = None
        try:
            if _has_live_activity(child) or not _valid_job_dir(child):
                continue
            modified = _latest_descendant_mtime(child)
            if modified is not None and modified >= cutoff:
                continue
            removed_path = child.absolute()
            moved = root / f"{DELETING_PREFIX}{claim_id}-{child.name}"
            os.replace(child, moved)
            shutil.rmtree(moved)
            moved = None
            removed.append(removed_path)
        finally:
            if moved is not None and moved.exists() and not child.exists():
                try:
                    os.replace(moved, child)
                except OSError:
                    pass
            if child.exists():
                (child / CLEANUP_MARKER_NAME).unlink(missing_ok=True)
    return removed


def cleanup_expired(
    *,
    retention_hours: float = DEFAULT_RETENTION_HOURS,
    now: float | None = None,
) -> list[Path]:
    current = time.time() if now is None else now
    if not math.isfinite(retention_hours) or retention_hours <= 0:
        raise ValueError("retention_hours must be a positive finite number")
    if not math.isfinite(current) or current <= 0:
        raise ValueError("now must be a positive finite number")
    root = temp_root()
    cutoff = current - retention_hours * 3600
    lock_path = root / ROOT_CLEANUP_LOCK_NAME
    lock_handle = lock_path.open("a+b")
    locked = False
    try:
        locked = _lock_file(lock_handle, nonblocking=True)
        if not locked:
            return []
        return _cleanup_expired_locked(root, cutoff, current)
    finally:
        if locked:
            _unlock_file(lock_handle)
        lock_handle.close()
