import importlib.util
import io
import json
from email.message import Message
from pathlib import Path
import socket
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
from urllib import error
from PIL import Image

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
MODULE_PATH = SCRIPTS / "gemini_image_qc.py"
SPEC = importlib.util.spec_from_file_location("gemini_image_qc", MODULE_PATH)
qc = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(qc)


class Response:
    def __init__(self, payload: object):
        self.payload = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self.payload


def valid_review() -> dict[str, object]:
    return {
        "axis_scores": {"goal_fit": 5, "text_accuracy": 5, "material_realism": 4, "layout": 4},
        "rendered_text_exists": False,
        "observations": ["The subject is centered with no visible clipping."],
    }


def gemini_payload(review: dict[str, object]) -> dict[str, object]:
    return {"candidates": [{"content": {"parts": [{"text": json.dumps(review)}]}}]}


class GeminiImageQcTests(unittest.TestCase):
    def make_image(self, root: Path, color: tuple[int, int, int] = (20, 30, 40)) -> Path:
        image = root / "image.png"
        Image.new("RGB", (16, 12), color).save(image)
        return image

    def test_dry_run_is_network_free_and_binds_original_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            image = self.make_image(Path(tmp))
            with patch("sys.stdout", new_callable=io.StringIO) as stdout:
                self.assertEqual(qc.main([str(image), "--brief", "Catalog product image"]), 0)
            first = json.loads(stdout.getvalue())
            Image.new("RGB", (16, 12), (200, 10, 10)).save(image)
            with patch("sys.stdout", new_callable=io.StringIO) as stdout:
                self.assertEqual(qc.main([str(image), "--brief", "Catalog product image"]), 0)
            second = json.loads(stdout.getvalue())
        self.assertEqual(first["state"], "dry_run")
        self.assertNotEqual(first["request_sha256"], second["request_sha256"])
        self.assertEqual(first["thumbnail"], "ephemeral JPEG only")
    def test_thumbnail_is_compact_jpeg_and_preserves_original(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            original = root / "delivery.png"
            Image.new("RGBA", (1600, 1200), (30, 60, 90, 128)).save(original)
            before = original.read_bytes()
            thumbnail = root / "thumbnail.jpg"
            payload = qc.create_compact_thumbnail(original, thumbnail)
            with Image.open(thumbnail) as rendered:
                self.assertEqual(rendered.format, "JPEG")
                self.assertLessEqual(max(rendered.size), qc.THUMBNAIL_MAX_EDGE)
            self.assertEqual(payload, thumbnail.read_bytes())
            self.assertLessEqual(len(payload), qc.MAX_THUMBNAIL_BYTES)
            self.assertEqual(original.read_bytes(), before)
    def test_thumbnail_reencodes_until_it_meets_byte_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            original = root / "delivery.png"
            Image.effect_noise((1600, 1200), 100).save(original)
            thumbnail = root / "thumbnail.jpg"
            with patch.object(qc, "MAX_THUMBNAIL_BYTES", 10_000):
                payload = qc.create_compact_thumbnail(original, thumbnail)
            self.assertLessEqual(len(payload), 10_000)
            with Image.open(thumbnail) as rendered:
                self.assertLess(max(rendered.size), qc.THUMBNAIL_MAX_EDGE)


    def test_primary_success_parses_and_skips_luna(self):
        seen = []
        def urlopen(http_request, *, timeout):
            seen.append((http_request, timeout))
            return Response(gemini_payload(valid_review()))
        primary = qc.run_gemini_primary("same QC question", b"jpeg", "oauth-token", 10, urlopen=urlopen)
        luna = Mock()
        reviewed, route = qc.review_thumbnail(
            "same QC question", Path("/tmp/thumb.jpg"), b"jpeg", "oauth-token", 10, 20, None,
            primary=lambda *_args: primary, luna=luna,
        )
        self.assertEqual(route, "gemini_primary")
        self.assertEqual(reviewed["report"]["qc_status"], "passed")
        luna.assert_not_called()
        self.assertEqual(seen[0][1], 10)
        self.assertEqual(seen[0][0].full_url, qc.GEMINI_ENDPOINT)
        self.assertEqual(seen[0][0].get_header("X-goog-api-key"), "oauth-token")
        self.assertNotIn("oauth-token", seen[0][0].full_url)
        primary_body = json.loads(seen[0][0].data)
        image_part = primary_body["contents"][0]["parts"][1]
        self.assertEqual(image_part["inlineData"]["mimeType"], "image/jpeg")
        self.assertNotIn("inline_data", image_part)

    def test_api_key_is_redacted_from_errors_and_serialized_results(self):
        secret = "sentinel-gemini-secret"
        def urlopen(*_args, **_kwargs):
            raise error.HTTPError(qc.GEMINI_ENDPOINT, 400, secret, Message(), None)
        with self.assertRaises(qc.PrimaryReviewError) as caught:
            qc.run_gemini_primary("q", b"jpeg", secret, 10, urlopen=urlopen)
        self.assertNotIn(secret, str(caught.exception))
        self.assertNotIn(secret, json.dumps(caught.exception.args))

    def test_primary_timeout_invokes_luna_subprocess_once(self):
        calls = []
        completed = type("Completed", (), {
            "returncode": 0,
            "stdout": json.dumps({"type": "item.completed", "item": {"type": "agent_message", "text": json.dumps(valid_review())}}),
            "stderr": "",
        })()
        def runner(*args, **kwargs):
            calls.append((args, kwargs))
            return completed
        def primary(*_args):
            raise qc.PrimaryReviewError("Gemini primary timed out.", transient=True)
        def luna(question, thumbnail, timeout, codex_bin):
            with patch.object(qc, "resolve_codex_command", return_value=type("Resolved", (), {"command": "/tools/codex"})()):
                return qc.run_luna_fallback(question, thumbnail, timeout, codex_bin, runner=runner)
        reviewed, route = qc.review_thumbnail(
            "same QC question", Path("/tmp/thumb.jpg"), b"jpeg", "oauth-token", 10, 20, None,
            primary=primary, luna=luna,
        )
        self.assertEqual(route, "luna_fallback")
        self.assertEqual(reviewed["report"]["qc_status"], "passed")
        self.assertEqual(len(calls), 1)
        command = calls[0][0][0]
        self.assertIn('model="gpt-5.6-luna"', command)
        self.assertIn("--image", command)
        self.assertTrue(calls[0][1]["capture_output"])
        self.assertFalse(calls[0][1]["check"])

    def test_hard_primary_4xx_does_not_fallback(self):
        def urlopen(*_args, **_kwargs):
            raise error.HTTPError(qc.GEMINI_ENDPOINT, 400, "bad request", {}, None)
        luna = Mock()
        def primary(question, thumbnail, token, timeout):
            return qc.run_gemini_primary(question, thumbnail, token, timeout, urlopen=urlopen)
        with self.assertRaisesRegex(qc.PrimaryReviewError, "HTTP 400"):
            qc.review_thumbnail(
                "same QC question", Path("/tmp/thumb.jpg"), b"jpeg", "oauth-token", 10, 20, None,
                primary=primary, luna=luna,
            )
        luna.assert_not_called()

    def test_malformed_primary_response_fails_closed_without_luna(self):
        luna = Mock()
        def primary(question, thumbnail, token, timeout):
            return qc.run_gemini_primary(question, thumbnail, token, timeout, urlopen=lambda *_args, **_kwargs: Response({"candidates": []}))
        with self.assertRaisesRegex(qc.PrimaryReviewError, "malformed"):
            qc.review_thumbnail(
                "same QC question", Path("/tmp/thumb.jpg"), b"jpeg", "oauth-token", 10, 20, None,
                primary=primary, luna=luna,
            )
        luna.assert_not_called()

    def test_malformed_luna_output_fails_closed(self):
        completed = type("Completed", (), {"returncode": 0, "stdout": "not json", "stderr": ""})()
        with patch.object(qc, "resolve_codex_command", return_value=type("Resolved", (), {"command": "/tools/codex"})()):
            with self.assertRaisesRegex(qc.ImageQcError, "structured agent message"):
                qc.run_luna_fallback("same QC question", Path("/tmp/thumb.jpg"), 20, None, runner=lambda *_args, **_kwargs: completed)

    def test_primary_429_and_5xx_invoke_one_fallback(self):
        for status in (429, 500, 503):
            with self.subTest(status=status):
                def urlopen(*_args, **_kwargs):
                    raise error.HTTPError(qc.GEMINI_ENDPOINT, status, "transient", {}, None)
                luna = Mock(return_value=qc.parse_review_response(json.dumps(valid_review())))
                def primary(question, thumbnail, token, timeout):
                    return qc.run_gemini_primary(question, thumbnail, token, timeout, urlopen=urlopen)
                reviewed, route = qc.review_thumbnail(
                    "same QC question", Path("/tmp/thumb.jpg"), b"jpeg", "oauth-token", 10, 20, None,
                    primary=primary, luna=luna,
                )
                self.assertEqual(route, "luna_fallback")
                self.assertEqual(reviewed["report"]["qc_status"], "passed")
                luna.assert_called_once()

    def test_timeout_is_retryable(self):
        with self.assertRaisesRegex(qc.PrimaryReviewError, "timed out") as caught:
            qc.run_gemini_primary(
                "q", b"jpeg", "oauth-token", 10,
                urlopen=lambda *_args, **_kwargs: (_ for _ in ()).throw(socket.timeout()),
            )
        self.assertTrue(caught.exception.transient)


if __name__ == "__main__":
    unittest.main()
