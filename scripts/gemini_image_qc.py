#!/usr/bin/env python3
"""Fail-closed post-generation image QC with Gemini primary and Luna fallback.

The original image is never modified or uploaded as the review payload. Gemini receives
only an ephemeral compact JPEG thumbnail. A single Codex subscription Luna retry is
allowed only after a primary timeout, HTTP 429, or HTTP 5xx response.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import re
import socket
import stat
import subprocess
import sys
import tempfile
import time
from typing import Callable, Mapping, Sequence
from urllib import error, request

import codex_subscription_transport as transport
from codex_cli_resolver import CodexResolutionError, resolve_codex_command

APPROVAL_ENV = "HERMES_GEMINI_IMAGE_QC_APPROVAL_SHA256"
GEMINI_API_KEY_ENVS = ("GOOGLE_API_KEY", "GEMINI_API_KEY")
GEMINI_MODEL = "gemini-3-flash-preview"
LUNA_MODEL = "gpt-5.6-luna"
GEMINI_ENDPOINT = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
PROMPT_VERSION = 3
MAX_IMAGE_BYTES = 20 * 1024 * 1024
MAX_THUMBNAIL_BYTES = 300 * 1024
MAX_RESPONSE_CHARS = 128 * 1024
THUMBNAIL_MAX_EDGE = 1024
_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
QC_MODES = frozenset({"auto", "gemini-luna", "gemini", "luna", "off"})
QC_CONFIG_VERSION = 1


class ImageQcError(RuntimeError):
    """Raised when a QC request cannot be safely completed."""


class PrimaryReviewError(ImageQcError):
    def __init__(self, message: str, *, transient: bool = False) -> None:
        super().__init__(message)
        self.transient = transient

def default_qc_config_path() -> Path:
    return Path(__file__).resolve().parent.parent / "vision-qc.json"


def load_qc_config(config_path: Path | None) -> tuple[str, Path | None]:
    path = (config_path or default_qc_config_path()).expanduser()
    if not path.exists() and not path.is_symlink() and config_path is None:
        return "off", None
    try:
        mode = path.lstat().st_mode
        resolved = path.resolve(strict=True)
    except FileNotFoundError as exc:
        raise ImageQcError(f"Vision-QC config does not exist: {path}") from exc
    if stat.S_ISLNK(mode) or not resolved.is_file():
        raise ImageQcError(f"Vision-QC config must be a regular non-symlink file: {path}")
    try:
        value = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ImageQcError("Vision-QC config is not valid JSON.") from exc
    allowed = {"version", "qc_mode", "requested_mode"}
    if not isinstance(value, dict) or not {"version", "qc_mode"}.issubset(value) or not set(value).issubset(allowed):
        raise ImageQcError("Vision-QC config must contain only version, qc_mode, and optional requested_mode.")
    if type(value["version"]) is not int or value["version"] != QC_CONFIG_VERSION or not isinstance(value["qc_mode"], str) or value["qc_mode"] not in QC_MODES:
        raise ImageQcError("Vision-QC config has an unsupported version or qc_mode.")
    return value["qc_mode"], resolved


def configured_api_key() -> tuple[str | None, str]:
    for name in GEMINI_API_KEY_ENVS:
        value = os.environ.get(name, "")
        if value:
            return name, value
    return None, ""


def codex_is_available(codex_bin: str | Path | None = None) -> bool:
    try:
        resolve_codex_command(explicit=codex_bin)
        return True
    except CodexResolutionError:
        return False


def resolve_qc_mode(cli_mode: str | None, config_path: Path | None, codex_bin: str | Path | None = None) -> dict[str, object]:
    configured_mode, resolved_config = load_qc_config(config_path)
    env_mode = os.environ.get("HEITUZ_VISION_QC_MODE", "").strip() or None
    if env_mode is not None and env_mode not in QC_MODES:
        raise ImageQcError("HEITUZ_VISION_QC_MODE has an unsupported value.")
    requested_mode = cli_mode or env_mode or configured_mode
    source = "command_line" if cli_mode is not None else ("environment" if env_mode is not None else ("config" if resolved_config is not None else "default"))
    if requested_mode == "off":
        raise ImageQcError("Vision-QC is disabled by configuration; no review can be performed.")
    effective_mode = requested_mode
    if requested_mode == "auto":
        _, api_key = configured_api_key()
        has_codex = codex_is_available(codex_bin)
        effective_mode = "gemini-luna" if api_key and has_codex else ("gemini" if api_key else ("luna" if has_codex else "off"))
        if effective_mode == "off":
            raise ImageQcError("Vision-QC auto mode found neither a Gemini API key nor an available Codex CLI.")
    return {
        "requested": requested_mode,
        "effective": effective_mode,
        "source": source,
        "config": str(resolved_config) if resolved_config is not None else None,
    }



def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def file_digest(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def image_dimensions(path: Path) -> tuple[int, int]:
    try:
        from PIL import Image
        with Image.open(path) as image:
            return image.size
    except (ImportError, OSError, ValueError) as exc:
        raise ImageQcError("Could not read image dimensions.") from exc


def validate_image(image: Path) -> Path:
    candidate = image.expanduser()
    try:
        mode = candidate.lstat().st_mode
        resolved = candidate.resolve(strict=True)
    except FileNotFoundError as exc:
        raise ImageQcError(f"Image does not exist: {image}") from exc
    if stat.S_ISLNK(mode) or not resolved.is_file():
        raise ImageQcError(f"Image must be a regular non-symlink file: {image}")
    if resolved.suffix.lower() not in _IMAGE_SUFFIXES:
        raise ImageQcError("Image must be a PNG, JPEG, or WebP file.")
    size = resolved.stat().st_size
    if not 0 < size <= MAX_IMAGE_BYTES:
        raise ImageQcError(f"Image must be between 1 byte and {MAX_IMAGE_BYTES} bytes.")
    return resolved


def _normalize_text(value: str, *, field: str, limit: int) -> str:
    normalized = value.strip()
    if not normalized:
        raise ImageQcError(f"{field} must not be empty.")
    if len(normalized) > limit:
        raise ImageQcError(f"{field} must be at most {limit} characters.")
    return normalized


def build_request(image: Path, brief: str, expected_text: Sequence[str], job_id: str | None, qc_mode: str = "gemini") -> dict[str, object]:
    image_digest, image_size = file_digest(image)
    image_width, image_height = image_dimensions(image)
    normalized_text = [_normalize_text(item, field="Expected text", limit=1_000) for item in expected_text]
    if len(normalized_text) != len(set(normalized_text)):
        raise ImageQcError("Expected text entries must be unique.")
    if job_id is not None:
        job_id = _normalize_text(job_id, field="Job id", limit=128)
        if not _ID_RE.fullmatch(job_id):
            raise ImageQcError("Job id must use letters, digits, dots, underscores, or hyphens.")
    return {
        "prompt_version": PROMPT_VERSION,
        "image": {
            "path": str(image), "sha256": image_digest, "bytes": image_size,
            "width": image_width, "height": image_height,
        },
        "brief": _normalize_text(brief, field="Brief", limit=8_000),
        "expected_text": normalized_text,
        "id": job_id,
        "qc_mode": qc_mode,
    }


def request_digest(review_request: Mapping[str, object]) -> str:
    return hashlib.sha256(canonical_json(review_request).encode("utf-8")).hexdigest()


def build_question(review_request: Mapping[str, object]) -> str:
    expected_text = review_request["expected_text"]
    assert isinstance(expected_text, list)
    return (
        "Review this generated image for production quality. Use only visible evidence. "
        "Score each axis from 0 through 5, where 5 is production-ready: goal_fit against "
        "the brief, text_accuracy against expected text, material_realism, and layout. "
        "Return only one JSON object with exactly these keys: axis_scores, "
        "rendered_text_exists, observations. axis_scores must contain exactly goal_fit, "
        "text_accuracy, material_realism, layout. rendered_text_exists must be boolean. "
        "observations must be one to eight concise evidence-based strings. "
        f"Brief: {review_request['brief']}\nExpected text: {json.dumps(expected_text, ensure_ascii=False)}"
    )


def create_compact_thumbnail(image: Path, destination: Path) -> bytes:
    """Encode a bounded JPEG copy; the source image remains untouched."""
    try:
        from PIL import Image
    except ImportError as exc:  # pragma: no cover - depends on local optional dependency
        raise ImageQcError("Pillow is required to create the compact JPEG QC thumbnail.") from exc
    try:
        with Image.open(image) as source:
            source.thumbnail((THUMBNAIL_MAX_EDGE, THUMBNAIL_MAX_EDGE))
            if source.mode in {"RGBA", "LA"} or (source.mode == "P" and "transparency" in source.info):
                background = Image.new("RGB", source.size, "white")
                alpha = source.convert("RGBA").getchannel("A")
                background.paste(source.convert("RGB"), mask=alpha)
                thumbnail = background
            else:
                thumbnail = source.convert("RGB")
            working = thumbnail
            for _ in range(8):
                for quality in (82, 70, 55, 40):
                    working.save(destination, format="JPEG", quality=quality, optimize=True, progressive=True)
                    payload = destination.read_bytes()
                    if payload and len(payload) <= MAX_THUMBNAIL_BYTES:
                        return payload
                width, height = working.size
                if width == 1 and height == 1:
                    break
                working = working.resize((max(1, width * 3 // 4), max(1, height * 3 // 4)))
    except (OSError, ValueError) as exc:
        raise ImageQcError("Could not create a JPEG QC thumbnail from the image.") from exc
    raise ImageQcError("Compact JPEG QC thumbnail exceeds the 300 KiB limit.")


def _strip_fence(raw: str) -> str:
    candidate = raw.strip()
    if candidate.startswith("```json") and candidate.endswith("```"):
        return candidate[7:-3].strip()
    if candidate.startswith("```") and candidate.endswith("```"):
        return candidate[3:-3].strip()
    return candidate


def parse_review_response(raw: str) -> dict[str, object]:
    if len(raw) > MAX_RESPONSE_CHARS:
        raise ImageQcError("Vision response exceeds the maximum accepted size.")
    try:
        value = json.loads(_strip_fence(raw))
    except json.JSONDecodeError as exc:
        raise ImageQcError("Vision response must be one valid JSON object.") from exc
    if not isinstance(value, dict):
        raise ImageQcError("Vision response must be a JSON object.")
    expected = {"axis_scores", "rendered_text_exists", "observations"}
    if set(value) != expected:
        raise ImageQcError("Vision response must contain exactly axis_scores, rendered_text_exists, observations.")
    scores = value["axis_scores"]
    rendered_text_exists = value["rendered_text_exists"]
    observations = value["observations"]
    if not isinstance(scores, dict):
        raise ImageQcError("Vision axis_scores must be an object.")
    if not isinstance(rendered_text_exists, bool):
        raise ImageQcError("Vision rendered_text_exists must be a boolean.")
    if not isinstance(observations, list) or not 1 <= len(observations) <= 8:
        raise ImageQcError("Vision observations must contain one to eight strings.")
    normalized_observations = [_normalize_text(item, field="Observation", limit=500) if isinstance(item, str) else None for item in observations]
    if any(item is None for item in normalized_observations):
        raise ImageQcError("Vision observations must contain only strings.")
    try:
        report = transport.evaluate_qc(scores, rendered_text_exists=rendered_text_exists)
    except ValueError as exc:
        raise ImageQcError(f"Invalid vision QC scores: {exc}") from None
    return {"report": report, "observations": normalized_observations}


def _primary_response_text(payload: bytes) -> str:
    try:
        value = json.loads(payload)
        candidates = value["candidates"]
        candidate = candidates[0]
        parts = candidate["content"]["parts"]
        text = "".join(part["text"] for part in parts if isinstance(part, dict) and isinstance(part.get("text"), str))
    except (IndexError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise PrimaryReviewError("Gemini primary response is malformed.") from exc
    if not text:
        raise PrimaryReviewError("Gemini primary response contains no review text.")
    return text


def run_gemini_primary(question: str, thumbnail: bytes, api_key: str, timeout_seconds: int, *, urlopen: Callable[..., object] = request.urlopen) -> dict[str, object]:
    if not api_key.strip():
        raise PrimaryReviewError("GOOGLE_API_KEY or GEMINI_API_KEY must be set for Gemini primary QC.")
    if not 1 <= timeout_seconds <= 120:
        raise PrimaryReviewError("Primary timeout must be between 1 and 120 seconds.")
    body = canonical_json({
        "contents": [{"role": "user", "parts": [
            {"text": question},
            {"inlineData": {"mimeType": "image/jpeg", "data": base64.b64encode(thumbnail).decode("ascii")}},
        ]}],
        "generationConfig": {"temperature": 0, "responseMimeType": "application/json"},
    }).encode("utf-8")
    http_request = request.Request(GEMINI_ENDPOINT, data=body, method="POST", headers={
        "x-goog-api-key": api_key, "Content-Type": "application/json",
    })
    try:
        with urlopen(http_request, timeout=timeout_seconds) as response:
            return parse_review_response(_primary_response_text(response.read()))
    except error.HTTPError as exc:
        transient = exc.code == 429 or 500 <= exc.code <= 599
        raise PrimaryReviewError(f"Gemini primary returned HTTP {exc.code}.", transient=transient) from exc
    except (TimeoutError, socket.timeout) as exc:
        raise PrimaryReviewError("Gemini primary timed out.", transient=True) from exc
    except error.URLError as exc:
        if isinstance(exc.reason, (TimeoutError, socket.timeout)):
            raise PrimaryReviewError("Gemini primary timed out.", transient=True) from exc
        raise PrimaryReviewError("Gemini primary could not be reached.") from exc


def _codex_agent_message(cli_output: str) -> str:
    messages: list[str] = []
    for line in cli_output.splitlines():
        try:
            event = json.loads(line)
            item = event.get("item") if isinstance(event, dict) else None
            if event.get("type") == "item.completed" and isinstance(item, dict) and item.get("type") == "agent_message":
                text = item.get("text")
                if isinstance(text, str):
                    messages.append(text)
        except (AttributeError, json.JSONDecodeError):
            continue
    if len(messages) != 1:
        raise ImageQcError("Luna fallback did not return exactly one structured agent message.")
    return messages[0]


def run_luna_fallback(question: str, thumbnail: Path, timeout_seconds: int, codex_bin: str | Path | None, *, runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run) -> dict[str, object]:
    if not 1 <= timeout_seconds <= 900:
        raise ImageQcError("Luna timeout must be between 1 and 900 seconds.")
    try:
        resolved = resolve_codex_command(codex_bin)
    except CodexResolutionError as exc:
        raise ImageQcError(str(exc)) from None
    instruction = (
        "Use the attached image only for independent visual QC. Do not generate or edit an image, "
        "do not call image_generation, and return only the requested JSON object. " + question
    )
    command = [
        resolved.command, "exec", "--skip-git-repo-check", "--ephemeral", "--json",
        "--config", f'model="{LUNA_MODEL}"', "--sandbox", "read-only", "--cd", str(thumbnail.parent),
        "--image", str(thumbnail), "--", instruction,
    ]
    try:
        completed = runner(command, cwd=thumbnail.parent, text=True, capture_output=True, timeout=timeout_seconds, check=False)
    except subprocess.TimeoutExpired as exc:
        raise ImageQcError("Luna fallback timed out.") from exc
    except OSError as exc:
        raise ImageQcError("Luna fallback could not be started.") from exc
    if completed.returncode != 0:
        category = transport.classify_cli_failure(completed.stdout, completed.stderr)
        raise ImageQcError(f"Luna fallback failed; category={category}; raw output withheld.")
    return parse_review_response(_codex_agent_message(completed.stdout))


def review_thumbnail(question: str, thumbnail: Path, thumbnail_bytes: bytes, api_key: str, primary_timeout: int, luna_timeout: int, codex_bin: str | Path | None, *, primary: Callable[..., dict[str, object]] = run_gemini_primary, luna: Callable[..., dict[str, object]] = run_luna_fallback) -> tuple[dict[str, object], str]:
    try:
        return primary(question, thumbnail_bytes, api_key, primary_timeout), "gemini_primary"
    except PrimaryReviewError as exc:
        if not exc.transient:
            raise
    return luna(question, thumbnail, luna_timeout, codex_bin), "luna_fallback"


def atomic_write_json(path: Path, value: object) -> None:
    if path.exists():
        raise ImageQcError(f"Refusing to overwrite existing report: {path}")
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    try:
        with temporary.open("x", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError as exc:
            raise ImageQcError(f"Refusing to overwrite existing report: {path}") from exc
    finally:
        temporary.unlink(missing_ok=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path, help="Full original PNG, JPEG, or WebP delivery artifact.")
    parser.add_argument("--brief", required=True, help="Production goal used for the goal-fit score.")
    parser.add_argument("--expected-text", action="append", default=[], help="Exact text expected in the image; repeatable.")
    parser.add_argument("--id", help="Optional batch job id; makes the output usable as QC JSONL.")
    parser.add_argument("--output", type=Path, help="New one-line JSONL report path; otherwise write to stdout.")
    parser.add_argument("--codex-bin", type=Path, help="Official Codex CLI executable used only for Luna review.")
    parser.add_argument("--qc-mode", choices=sorted(QC_MODES), help="Override the configured QC mode.")
    parser.add_argument("--qc-config", type=Path, help="Vision-QC JSON config path; default is the platform user config.")
    parser.add_argument("--primary-timeout-seconds", type=int, default=45)
    parser.add_argument("--luna-timeout-seconds", type=int, default=120)
    parser.add_argument("--execute", action="store_true", help="Run approved external QC; default is dry-run.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        image = validate_image(args.image)
        output = args.output.expanduser().resolve() if args.output is not None else None
        if output is not None and (output.exists() or not output.parent.is_dir()):
            raise ImageQcError(f"Report path must be new and its directory must exist: {output}")
        mode = resolve_qc_mode(args.qc_mode, args.qc_config, args.codex_bin)
        review_request = build_request(image, args.brief, args.expected_text, args.id, str(mode["effective"]))
        digest = request_digest(review_request)
        if not args.execute:
            print(json.dumps({"state": "dry_run", "request_sha256": digest, "approval_env": APPROVAL_ENV, "image": review_request["image"], "thumbnail": "ephemeral JPEG only", "qc_mode": mode}, ensure_ascii=False, indent=2))
            return 0
        # QC is an internal consequence of the authorized generation. Keep the
        # request digest for provenance; do not require a second approval.
        with tempfile.TemporaryDirectory(prefix="heituz-qc-") as tmp:
            thumbnail = Path(tmp) / "qc-thumbnail.jpg"
            thumbnail_bytes = create_compact_thumbnail(image, thumbnail)
            thumbnail_sha256, thumbnail_size = file_digest(thumbnail)
            thumbnail_width, thumbnail_height = image_dimensions(thumbnail)
            review_started = time.monotonic()
            if mode["effective"] == "gemini-luna":
                _, api_key = configured_api_key()
                if not api_key:
                    raise ImageQcError("Gemini-Luna mode requires GOOGLE_API_KEY or GEMINI_API_KEY.")
                reviewed, route = review_thumbnail(build_question(review_request), thumbnail, thumbnail_bytes, api_key, args.primary_timeout_seconds, args.luna_timeout_seconds, args.codex_bin)
            elif mode["effective"] == "gemini":
                _, api_key = configured_api_key()
                if not api_key:
                    raise ImageQcError("Gemini mode requires GOOGLE_API_KEY or GEMINI_API_KEY.")
                reviewed = run_gemini_primary(build_question(review_request), thumbnail_bytes, api_key, args.primary_timeout_seconds)
                route = "gemini_primary"
            elif mode["effective"] == "luna":
                reviewed = run_luna_fallback(build_question(review_request), thumbnail, args.luna_timeout_seconds, args.codex_bin)
                route = "luna_primary"
            else:
                raise ImageQcError("Unsupported effective Vision-QC mode.")
            elapsed_seconds = round(time.monotonic() - review_started, 3)
        report_raw = reviewed.get("report")
        if not isinstance(report_raw, dict):
            raise ImageQcError("Vision review report is malformed.")
        report: dict[str, object] = dict(report_raw)
        report.update({
            "schema_version": 3, "reviewer": route,
            "requested_primary_model": GEMINI_MODEL if mode["effective"] in {"gemini", "gemini-luna"} else LUNA_MODEL,
            "requested_fallback_model": LUNA_MODEL if mode["effective"] == "gemini-luna" else None,
            "model_identity_attested": False, "request_sha256": digest, "reviewed_image": review_request["image"],
            "qc_mode": {key: mode[key] for key in ("requested", "effective", "source")},
            "elapsed_seconds": elapsed_seconds,
            "reviewed_thumbnail": {
                "sha256": thumbnail_sha256, "bytes": thumbnail_size,
                "width": thumbnail_width, "height": thumbnail_height,
            },
            "brief": review_request["brief"], "expected_text": review_request["expected_text"],
            "observations": reviewed["observations"], "reviewed_at": datetime.now(timezone.utc).isoformat(),
        })
        if review_request["id"] is not None:
            report["id"] = review_request["id"]
        if output is None:
            print(canonical_json(report))
        else:
            atomic_write_json(output, report)
        return 0
    except ImageQcError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
