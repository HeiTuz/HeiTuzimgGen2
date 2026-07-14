import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import codex_subscription_batch as batch
import folder_batch_prepare
import output_lifecycle


class FolderBatchPrepareTests(unittest.TestCase):
    def _managed(self, tmp: str):
        return patch.object(output_lifecycle.tempfile, "gettempdir", return_value=tmp)

    def test_recursive_folder_prepares_temp_manifest_without_touching_sources(self):
        with tempfile.TemporaryDirectory() as tmp, self._managed(tmp):
            source = Path(tmp) / "products"
            nested = source / "detail"
            nested.mkdir(parents=True)
            front = source / "front.jpg"
            detail = nested / "zipper.PNG"
            ignored = source / "notes.txt"
            front.write_bytes(b"front")
            detail.write_bytes(b"detail")
            ignored.write_text("ignore", encoding="utf-8")
            before = {path: path.read_bytes() for path in (front, detail)}

            result = folder_batch_prepare.prepare_folder_batch(
                source,
                "Remove only the background and return a transparent PNG.",
            )

            manifest = Path(result["manifest"])
            output_root = Path(result["output_root"])
            records = [json.loads(line) for line in manifest.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(result["source_count"], 2)
            self.assertTrue(result["temporary_outputs"])
            self.assertTrue(result["temporary_manifest"])
            self.assertEqual(output_root.parent, manifest.parent)
            self.assertEqual(
                [record["output_path"] for record in records],
                ["detail/zipper.png", "front.png"],
            )
            self.assertEqual(
                [record["images"] for record in records],
                [[str(detail.resolve())], [str(front.resolve())]],
            )
            jobs, _ = batch.load_manifest(manifest, output_root)
            self.assertEqual(len(jobs), 2)
            self.assertEqual(before, {path: path.read_bytes() for path in (front, detail)})
            self.assertFalse(any(output_root.rglob("*.png")))

    def test_explicit_output_inside_source_is_excluded_from_inventory(self):
        with tempfile.TemporaryDirectory() as tmp, self._managed(tmp):
            source = Path(tmp) / "products"
            output = source / "DINT_OUTPUT"
            output.mkdir(parents=True)
            (source / "front.jpg").write_bytes(b"front")
            stale = output / "stale.png"
            stale.write_bytes(b"stale")

            result = folder_batch_prepare.prepare_folder_batch(
                source,
                "Keep the product and replace the background.",
                output,
            )

            self.assertEqual(result["source_count"], 1)
            self.assertFalse(result["temporary_outputs"])
            self.assertFalse(result["temporary_manifest"])
            self.assertEqual(Path(result["output_root"]), output.resolve())
            manifest = Path(result["manifest"])
            self.assertTrue(manifest.is_relative_to(output.resolve()))
            self.assertEqual(manifest.parent.name, ".heituzimggen2-manifests")
            self.assertFalse((Path(tmp) / output_lifecycle.DEFAULT_TEMP_DIRNAME).exists())
            self.assertEqual(stale.read_bytes(), b"stale")

    def test_output_ancestor_does_not_exclude_source_inventory(self):
        with tempfile.TemporaryDirectory() as tmp, self._managed(tmp):
            shared = Path(tmp) / "shared"
            source = shared / "products"
            source.mkdir(parents=True)
            (source / "front.jpg").write_bytes(b"front")

            result = folder_batch_prepare.prepare_folder_batch(
                source,
                "Keep the product unchanged.",
                shared,
            )

            self.assertEqual(result["source_count"], 1)
            jobs, _ = batch.load_manifest(Path(result["manifest"]), shared)
            self.assertEqual(len(jobs), 1)

    def test_same_stem_sources_receive_unique_output_names(self):
        with tempfile.TemporaryDirectory() as tmp, self._managed(tmp):
            source = Path(tmp) / "products"
            source.mkdir()
            (source / "look.jpg").write_bytes(b"jpg")
            (source / "look.png").write_bytes(b"png")

            result = folder_batch_prepare.prepare_folder_batch(source, "Cut out the product.")
            manifest = Path(result["manifest"])
            records = [json.loads(line) for line in manifest.read_text(encoding="utf-8").splitlines()]

            self.assertEqual(
                [record["output_path"] for record in records],
                ["look-jpg.png", "look-png.png"],
            )
            jobs, _ = batch.load_manifest(manifest, Path(result["output_root"]))
            self.assertEqual(len(jobs), 2)

    def test_adversarial_names_still_produce_unique_valid_manifest(self):
        with tempfile.TemporaryDirectory() as tmp, self._managed(tmp):
            source = Path(tmp) / "products"
            source.mkdir()
            for name in ("a.jpg", "a.png", "a-jpg.webp", "a-jpg-509b0d46.webp"):
                (source / name).write_bytes(name.encode("utf-8"))

            result = folder_batch_prepare.prepare_folder_batch(source, "Cut out the product.")
            manifest = Path(result["manifest"])
            records = [json.loads(line) for line in manifest.read_text(encoding="utf-8").splitlines()]
            outputs = [record["output_path"].casefold() for record in records]

            self.assertEqual(len(outputs), len(set(outputs)))
            jobs, _ = batch.load_manifest(manifest, Path(result["output_root"]))
            self.assertEqual(len(jobs), 4)

    def test_hash_colliding_hostile_names_receive_unique_job_ids(self):
        with tempfile.TemporaryDirectory() as tmp, self._managed(tmp):
            source = Path(tmp) / "products"
            source.mkdir()
            for name in ("a_@[&x.jpg", "a_]])x.jpg"):
                (source / name).write_bytes(name.encode("utf-8"))

            result = folder_batch_prepare.prepare_folder_batch(source, "Cut out the product.")
            manifest = Path(result["manifest"])
            records = [json.loads(line) for line in manifest.read_text(encoding="utf-8").splitlines()]
            ids = [record["id"].casefold() for record in records]

            self.assertEqual(len(ids), len(set(ids)))
            jobs, _ = batch.load_manifest(manifest, Path(result["output_root"]))
            self.assertEqual(len(jobs), 2)

    def test_main_reports_filesystem_errors_as_json(self):
        with tempfile.TemporaryDirectory() as tmp, self._managed(tmp):
            source = Path(tmp) / "products"
            source.mkdir()
            (source / "front.jpg").write_bytes(b"front")
            blocked = Path(tmp) / "blocked-output"
            blocked.write_text("not a directory", encoding="utf-8")
            stderr = io.StringIO()

            with contextlib.redirect_stderr(stderr):
                status = folder_batch_prepare.main([
                    "--input-dir", str(source),
                    "--prompt", "Keep the product unchanged.",
                    "--output-root", str(blocked),
                ])

            self.assertEqual(status, 2)
            self.assertIn("error", json.loads(stderr.getvalue()))

    @unittest.skipUnless(os.name == "nt", "Windows junction behavior")
    def test_recursive_inventory_rejects_external_junction(self):
        with tempfile.TemporaryDirectory() as tmp, self._managed(tmp):
            source = Path(tmp) / "products"
            external = Path(tmp) / "external"
            source.mkdir()
            external.mkdir()
            secret = external / "secret.png"
            secret.write_bytes(b"secret")
            junction = source / "linked"
            result = subprocess.run(
                ["cmd.exe", "/c", "mklink", "/J", str(junction), str(external)],
                capture_output=True,
                text=True,
                errors="replace",
            )
            if result.returncode != 0:
                self.skipTest("Unable to create a Windows junction")

            with self.assertRaisesRegex(folder_batch_prepare.FolderPrepareError, "reparse point"):
                folder_batch_prepare.prepare_folder_batch(source, "Do not leak external files.")

            self.assertEqual(secret.read_bytes(), b"secret")

    def test_recursive_inventory_rejects_symlink_entry(self):
        with tempfile.TemporaryDirectory() as tmp, self._managed(tmp):
            source = Path(tmp) / "products"
            external = Path(tmp) / "external"
            source.mkdir()
            external.mkdir()
            (external / "secret.png").write_bytes(b"secret")
            link = source / "linked"
            try:
                link.symlink_to(external, target_is_directory=True)
            except OSError:
                self.skipTest("Unable to create a directory symlink")

            with self.assertRaisesRegex(folder_batch_prepare.FolderPrepareError, "symlink"):
                folder_batch_prepare.prepare_folder_batch(source, "Do not leak external files.")

    def test_folder_count_and_total_size_limits_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp, self._managed(tmp):
            source = Path(tmp) / "products"
            source.mkdir()
            (source / "one.jpg").write_bytes(b"12")
            (source / "two.jpg").write_bytes(b"34")

            with patch.object(folder_batch_prepare, "MAX_SOURCE_FILES", 1):
                with self.assertRaisesRegex(folder_batch_prepare.FolderPrepareError, "image safety limit"):
                    folder_batch_prepare.prepare_folder_batch(source, "Bound the input.")
            with patch.object(folder_batch_prepare, "MAX_TOTAL_SOURCE_BYTES", 3):
                with self.assertRaisesRegex(folder_batch_prepare.FolderPrepareError, "byte safety limit"):
                    folder_batch_prepare.prepare_folder_batch(source, "Bound the input.")

    def test_explicit_output_inside_managed_temp_root_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp, self._managed(tmp):
            source = Path(tmp) / "products"
            source.mkdir()
            (source / "front.jpg").write_bytes(b"front")
            managed = output_lifecycle.temp_root()

            with self.assertRaisesRegex(ValueError, "temporary root"):
                folder_batch_prepare.prepare_folder_batch(
                    source,
                    "Keep the product unchanged.",
                    managed / "persistent",
                )


if __name__ == "__main__":
    unittest.main()
