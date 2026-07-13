import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

MODULE_PATH = Path(__file__).with_name("codex_subscription_transport.py")
SPEC = importlib.util.spec_from_file_location("codex_subscription_transport", MODULE_PATH)
transport = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(transport)


class CodexSubscriptionTransportTests(unittest.TestCase):
    def test_dry_run_uses_supported_cli_and_honest_model_label(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(transport.shutil, "which", return_value="/bin/codex"):
            result = transport.run("draw a blue square", Path(tmp) / "image.png", [])
        self.assertEqual(result["transport"], "official-codex-cli-subscription")
        self.assertIsNone(result["requested_model"])
        self.assertIsNone(result["observed_model"])
        self.assertFalse(result["model_identity_attested"])
        self.assertIn("--skip-git-repo-check", result["command"])
        self.assertIn('model_reasoning_effort="medium"', result["command"])
        self.assertNotIn("--model", result["command"])
        self.assertNotIn("--enable", result["command"])
        self.assertNotIn("draw a blue square", " ".join(result["command"]))

    def test_live_call_requires_fresh_approval_marker(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(transport.shutil, "which", return_value="/bin/codex"), patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(transport.TransportError, transport.APPROVAL_ENV):
                transport.run("draw", Path(tmp) / "image.png", [], execute=True)

    def test_references_are_bounded_and_must_exist(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            refs = []
            for index in range(5):
                ref = root / f"ref-{index}.png"
                ref.write_bytes(b"x")
                refs.append(ref)
            with self.assertRaisesRegex(transport.TransportError, "At most four"):
                transport.validate_request("draw", root / "out.png", refs)

    def test_existing_output_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "out.png"
            output.write_bytes(b"existing")
            with self.assertRaisesRegex(transport.TransportError, "Refusing to overwrite"):
                transport.validate_request("draw", output, [])

    def test_cli_failure_classifies_without_echoing_subprocess_output(self):
        completed = transport.subprocess.CompletedProcess(
            [],
            7,
            stdout="request token=secret",
            stderr="The model unsupported-model is unavailable; cookie=secret",
        )
        with tempfile.TemporaryDirectory() as tmp, patch.object(transport.shutil, "which", return_value="/bin/codex"), patch.object(transport.subprocess, "run", return_value=completed), patch.dict(os.environ, {transport.APPROVAL_ENV: "1"}, clear=True):
            with self.assertRaisesRegex(transport.TransportError, "category=model_unavailable") as caught:
                transport.run("draw", Path(tmp) / "out.png", [], execute=True)
        self.assertNotIn("token=secret", str(caught.exception))
        self.assertNotIn("cookie=secret", str(caught.exception))
        self.assertNotIn("unsupported", str(caught.exception))

    def test_cli_failure_categories_are_secret_free(self):
        cases = {
            "authentication_required": ("", "Login required: bearer abc"),
            "entitlement_denied": ("", "Account does not have access; session=abc"),
            "rate_limited": ("", "Too many requests; token=abc"),
            "image_tool_unavailable": ("", "image_generation is disabled; cookie=abc"),
            "unknown_cli_failure": ("opaque secret payload", ""),
        }
        for expected, streams in cases.items():
            self.assertEqual(transport.classify_cli_failure(*streams), expected)

    def test_session_pngs_are_scoped_to_session_ids_in_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            mine = root / "019f5670-ef96-7530-8c39-962ed2b739a1"
            other = root / "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
            mine.mkdir()
            other.mkdir()
            (mine / "img.png").write_bytes(b"mine")
            (other / "img.png").write_bytes(b"other")
            found = transport.session_pngs(
                '{"thread_id":"019f5670-ef96-7530-8c39-962ed2b739a1"}', root
            )
            self.assertEqual(found, {(mine / "img.png").resolve()})

    def test_timeout_is_converted_to_transport_error(self):
        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(transport.shutil, "which", return_value="/bin/codex"), \
                patch.object(transport.subprocess, "run",
                             side_effect=transport.subprocess.TimeoutExpired(cmd="codex", timeout=1)), \
                patch.dict(os.environ, {transport.APPROVAL_ENV: "1"}, clear=True):
            with self.assertRaisesRegex(transport.TransportError, "timed out"):
                transport.run("draw", Path(tmp) / "out.png", [], execute=True)

    def test_empty_artifacts_are_ignored(self):
        completed = transport.subprocess.CompletedProcess([], 0, stdout="", stderr="")
        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(transport.shutil, "which", return_value="/bin/codex"), \
                patch.object(transport.subprocess, "run", return_value=completed), \
                patch.object(transport, "GENERATED_IMAGES_DIR", Path(tmp) / "gen"), \
                patch.dict(os.environ, {transport.APPROVAL_ENV: "1"}, clear=True):
            gen_dir = Path(tmp) / "gen" / "019f5670-ef96-7530-8c39-962ed2b739a1"
            gen_dir.mkdir(parents=True)
            (gen_dir / "empty.png").write_bytes(b"")
            with self.assertRaisesRegex(transport.TransportError, "did not produce"):
                transport.run("draw", Path(tmp) / "out.png", [], execute=True)


if __name__ == "__main__":
    unittest.main()
