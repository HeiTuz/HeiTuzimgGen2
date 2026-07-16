import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mpw_root


class MpwRootTests(unittest.TestCase):
    def make_install(self, root: Path) -> Path:
        root.mkdir()
        (root / "SKILL.md").write_text("---\nname: HeiTuzMPW\n---\n", encoding="utf-8")
        return root

    def test_blank_override_raises(self):
        with mock.patch.dict(os.environ, {"HEITUZ_MPW_ROOT": "  "}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "blank"):
                mpw_root.resolve_mpw_root()

    def test_nonexistent_override_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "missing"
            with mock.patch.dict(os.environ, {"HEITUZ_MPW_ROOT": str(missing)}, clear=True):
                with self.assertRaisesRegex(RuntimeError, "not an existing HeiTuzMPW installation"):
                    mpw_root.resolve_mpw_root()

    def test_existing_non_mpw_override_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {"HEITUZ_MPW_ROOT": tmp}, clear=True):
                with self.assertRaisesRegex(RuntimeError, "not an existing HeiTuzMPW installation"):
                    mpw_root.resolve_mpw_root()

    def test_standard_resolution_prefers_hermes_installation(self):
        expected = Path.home() / ".hermes" / "skills" / "prompt-writing" / "HeiTuzMPW"
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(mpw_root.resolve_mpw_root(), expected)

    def test_empty_environment_and_home_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {"HOME": tmp}, clear=True):
                self.assertIsNone(mpw_root.resolve_mpw_root())

    def test_found_install_without_manifest_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_install(Path(tmp) / "HeiTuzMPW")
            with mock.patch.dict(os.environ, {"HEITUZ_MPW_ROOT": str(root)}, clear=True):
                resolved = mpw_root.resolve_mpw_root()
            with self.assertRaisesRegex(RuntimeError, "incomplete HeiTuzMPW installation"):
                mpw_root.require_contracts_manifest(resolved)


if __name__ == "__main__":
    unittest.main()
