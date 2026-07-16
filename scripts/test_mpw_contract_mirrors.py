import hashlib
import json
from pathlib import Path
import unittest

try:
    from mpw_root import no_installation_message, resolve_mpw_root
except ModuleNotFoundError:
    from scripts.mpw_root import no_installation_message, resolve_mpw_root


SKILL_ROOT = Path(__file__).resolve().parents[1]
MIRRORS = (
    ("references/apparel-handoff.schema.json", "v1/apparel-handoff.schema.json"),
    ("references/fixtures/apparel-handoff.valid.json", "v1/fixtures/apparel-handoff.valid.json"),
    ("contracts/v1/image-production-handoff.schema.json", "v1/image-production-handoff.schema.json"),
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class MPWContractMirrorTests(unittest.TestCase):
    def setUp(self):
        self.mpw_root = resolve_mpw_root()
        if self.mpw_root is None:
            self.skipTest(no_installation_message())

        manifest_path = self.mpw_root / "contracts" / "manifest.json"
        if not manifest_path.is_file():
            self.skipTest(f"SKIP: HeiTuzMPW manifest not found: {manifest_path}")
        self.manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.manifest_files = self.manifest.get("files", {})

    def test_imggen2_mirrors_match_mpw_manifest(self):
        contract_release = self.manifest.get("contract_release")
        for mirror_name, authority_name in MIRRORS:
            with self.subTest(mirror=mirror_name):
                self.assertIn(
                    authority_name,
                    self.manifest_files,
                    f"MPW manifest is missing required contract entry: {authority_name}",
                )
                mirror_hash = sha256_file(SKILL_ROOT / mirror_name)
                authority_hash = self.manifest_files[authority_name]
                self.assertEqual(
                    mirror_hash,
                    authority_hash,
                    f"{mirror_name}: mirror sha256={mirror_hash}, MPW manifest sha256={authority_hash}; "
                    f"contract_release={contract_release}; the mirror has FORKED from the MPW authority "
                    "and must be re-synced from HeiTuzMPW/contracts.",
                )


if __name__ == "__main__":
    unittest.main()
