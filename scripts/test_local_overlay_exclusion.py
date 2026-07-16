"""Verify machine-local calibration overlays stay out of distributable artifacts."""

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class LocalOverlayExclusionTests(unittest.TestCase):
    def _temporary_source(self, temporary_root: Path) -> Path:
        source = temporary_root / "source"
        shutil.copytree(
            ROOT,
            source,
            ignore=shutil.ignore_patterns(
                ".git", ".gjc", ".omx", ".codegraph", "node_modules", "__pycache__"
            ),
        )
        probe = source / "references" / "probe.local.md"
        probe.write_text("machine-local calibration\n", encoding="utf-8")
        return source

    def test_local_overlay_is_excluded_from_npm_pack_and_offline_install(self):
        npm = shutil.which("npm")
        node = shutil.which("node")
        if npm is None:
            self.skipTest("npm is required to verify npm pack exclusion")
        if node is None:
            self.skipTest("node is required to verify offline installer exclusion")

        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            source = self._temporary_source(temporary_root)
            packed = subprocess.run(
                [npm, "pack", "--dry-run", "--json"],
                cwd=source,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(packed.returncode, 0, packed.stderr or packed.stdout)
            files = json.loads(packed.stdout)[0]["files"]
            packaged_paths = {entry["path"] for entry in files}
            self.assertIn("references/execution-contract.md", packaged_paths)
            self.assertNotIn("references/probe.local.md", packaged_paths)

            destination = temporary_root / "installed"
            installed = subprocess.run(
                [node, "scripts/install.mjs", "--offline", "--agent", "hermes", "--target", str(destination)],
                cwd=source,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(installed.returncode, 0, installed.stderr or installed.stdout)
            self.assertFalse((destination / "references" / "probe.local.md").exists())

    def test_canonical_skill_uses_local_overlay_contract_without_personal_defaults(self):
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("references/full-body-calibration.local.md", skill)
        for prohibited in ("for this user", "180cm", "170cm"):
            self.assertNotIn(prohibited, skill)


if __name__ == "__main__":
    unittest.main()
