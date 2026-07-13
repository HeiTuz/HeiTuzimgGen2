import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


SKILL_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = Path(__file__).with_name("codex_subscription_transport.py")
SPEC = importlib.util.spec_from_file_location("codex_subscription_transport_contract", MODULE_PATH)
transport = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(transport)


class SkillContractTests(unittest.TestCase):
    def _references(self, root: Path, count: int) -> list[Path]:
        references = []
        for index in range(count):
            reference = root / f"reference-{index}.png"
            reference.write_bytes(b"fixture")
            references.append(reference)
        return references

    def test_generation_dry_run_resolves_output_without_calling_subprocess(self):
        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(transport.shutil, "which", return_value="/usr/bin/codex"), \
                patch.object(transport.subprocess, "run") as run:
            root = Path(tmp)
            result = transport.run("generate a blue square", root / "result.png", [])
        run.assert_not_called()
        self.assertEqual(result["output"], str((root / "result.png").resolve()))
        self.assertEqual(result["reference_count"], 0)
        self.assertFalse(result["live"])

    def test_edit_and_two_to_four_references_are_forwarded(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(
            transport.shutil, "which", return_value="/usr/bin/codex"
        ):
            root = Path(tmp)
            for count in (1, 2, 3, 4):
                references = self._references(root, count)
                result = transport.run("edit using references", root / f"result-{count}.png", references)
                self.assertEqual(result["reference_count"], count)
                for reference in references:
                    self.assertIn(str(reference.resolve()), result["command"])

    def test_missing_reference_and_output_collision_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaisesRegex(transport.TransportError, "not a file"):
                transport.validate_request("edit", root / "result.png", [root / "missing.png"])
            output = root / "result.png"
            output.write_bytes(b"existing")
            with self.assertRaisesRegex(transport.TransportError, "Refusing to overwrite"):
                transport.validate_request("generate", output, [])

    def test_success_without_output_is_a_response_error(self):
        completed = transport.subprocess.CompletedProcess([], 0, stdout="{}", stderr="")
        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(transport.shutil, "which", return_value="/usr/bin/codex"), \
                patch.object(transport.subprocess, "run", return_value=completed), \
                patch.dict(transport.os.environ, {transport.APPROVAL_ENV: "1"}, clear=True):
            with self.assertRaisesRegex(transport.TransportError, "did not produce"):
                transport.run("generate", Path(tmp) / "missing.png", [], execute=True)

    def test_model_label_and_telegram_document_rules_are_explicit(self):
        skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        contract = (SKILL_ROOT / "references" / "execution-contract.md").read_text(encoding="utf-8")
        combined = skill + contract
        self.assertIn("model_identity_attested", combined)
        self.assertIn("observed_model", combined)
        self.assertIn("never turn a requested label into an attestation", combined)
        self.assertIn("send_message", combined)
        self.assertIn("document/file attachment", combined)
        self.assertIn("printing the path is not", combined)

    def test_prohibited_fallbacks_are_documented(self):
        text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8").lower()
        for boundary in ("api-key billing", "private endpoints", "dom automation", "cookie extraction"):
            self.assertIn(boundary, text)
        self.assertIn("never fall back", text)


class OutputPathTests(unittest.TestCase):
    def test_explicit_output_wins(self):
        target = Path("/tmp/explicit-output.png")
        self.assertEqual(transport.resolve_output("blue cup", target, None), target)

    def test_single_generation_defaults_to_downloads(self):
        resolved = transport.resolve_output("A blue ceramic cup!", None, None)
        self.assertEqual(resolved.parent, transport.DOWNLOADS_DIR)
        self.assertTrue(resolved.name.startswith("a-blue-ceramic-cup-"))
        self.assertTrue(resolved.name.endswith(".png"))

    def test_batch_work_uses_dated_subfolder(self):
        with tempfile.TemporaryDirectory() as tmp:
            batch_root = Path(tmp)
            resolved = transport.resolve_output("product shot", None, batch_root)
            self.assertEqual(resolved.parent.parent, batch_root)
            self.assertRegex(resolved.parent.name, r"^\d{8}$")
            self.assertTrue(resolved.parent.is_dir())

    def test_collisions_get_numeric_suffix(self):
        with tempfile.TemporaryDirectory() as tmp:
            existing = Path(tmp) / "img.png"
            existing.write_bytes(b"x")
            self.assertEqual(transport._dedupe(existing).name, "img-2.png")

if __name__ == "__main__":
    unittest.main()
