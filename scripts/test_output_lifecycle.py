import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import output_lifecycle


class OutputLifecycleTests(unittest.TestCase):
    def _managed(self, tmp: str):
        return patch.object(output_lifecycle.tempfile, "gettempdir", return_value=tmp)

    @staticmethod
    def _age_tree(path: Path, timestamp: float) -> None:
        for item in sorted(path.rglob("*"), reverse=True):
            if not item.is_symlink():
                os.utime(item, (timestamp, timestamp))
        os.utime(path, (timestamp, timestamp))

    def test_temp_root_is_canonical_dedicated_private_and_marked(self):
        with tempfile.TemporaryDirectory() as tmp, self._managed(tmp):
            root = output_lifecycle.temp_root()
            marker = root / output_lifecycle.ROOT_MARKER_NAME
            payload = json.loads(marker.read_text(encoding="utf-8"))

            self.assertEqual(root, Path(tmp).resolve() / output_lifecycle.DEFAULT_TEMP_DIRNAME)
            self.assertTrue(root.is_absolute())
            self.assertEqual(payload["application"], "HeiTuzImgGen2")
            self.assertEqual(payload["schema"], 1)

    def test_temp_root_rejects_symlink_instead_of_following_it(self):
        with tempfile.TemporaryDirectory() as tmp, self._managed(tmp):
            target = Path(tmp) / "employee-data"
            target.mkdir()
            root = Path(tmp).resolve() / output_lifecycle.DEFAULT_TEMP_DIRNAME
            try:
                root.symlink_to(target, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"directory symlinks unavailable: {exc}")

            with self.assertRaisesRegex(ValueError, "symlink|reparse"):
                output_lifecycle.temp_root()

            self.assertTrue(target.is_dir())

    def test_root_marker_rejects_boolean_schema(self):
        with tempfile.TemporaryDirectory() as tmp, self._managed(tmp):
            root = Path(tmp).resolve() / output_lifecycle.DEFAULT_TEMP_DIRNAME
            root.mkdir()
            (root / output_lifecycle.ROOT_MARKER_NAME).write_text(
                json.dumps({"application": "HeiTuzImgGen2", "schema": True}),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "schema"):
                output_lifecycle.temp_root()

    def test_malformed_job_marker_is_preserved_not_cleaned(self):
        with tempfile.TemporaryDirectory() as tmp, self._managed(tmp):
            job = output_lifecycle.create_job_dir("single")
            artifact = job / "keep.png"
            artifact.write_bytes(b"keep")
            marker = job / output_lifecycle.JOB_MARKER_NAME
            payload = json.loads(marker.read_text(encoding="utf-8"))
            payload["unexpected"] = "field"
            payload["created_at"] = "not-a-number"
            marker.write_text(json.dumps(payload), encoding="utf-8")
            self._age_tree(job, 100)

            removed = output_lifecycle.cleanup_expired(retention_hours=1, now=10_000)

            self.assertEqual(removed, [])
            self.assertTrue(artifact.is_file())

    def test_nonempty_unmarked_root_is_not_adopted(self):
        with tempfile.TemporaryDirectory() as tmp, self._managed(tmp):
            root = Path(tmp).resolve() / output_lifecycle.DEFAULT_TEMP_DIRNAME
            unrelated = root / "employee-project" / "keep.png"
            unrelated.parent.mkdir(parents=True)
            unrelated.write_bytes(b"keep")

            with self.assertRaisesRegex(ValueError, "unmarked|marker"):
                output_lifecycle.temp_root()

            self.assertTrue(unrelated.is_file())

    @unittest.skipUnless(os.name == "nt", "Windows ownership behavior")
    def test_unmarked_nonempty_windows_root_is_not_repermissioned(self):
        with tempfile.TemporaryDirectory() as tmp, self._managed(tmp):
            root = Path(tmp).resolve() / output_lifecycle.DEFAULT_TEMP_DIRNAME
            root.mkdir()
            (root / "employee-data.txt").write_text("keep", encoding="utf-8")
            with patch.object(output_lifecycle, "_verify_windows_owner"), patch.object(
                output_lifecycle, "_secure_windows_dacl"
            ) as secure:
                with self.assertRaisesRegex(ValueError, "non-empty unmarked"):
                    output_lifecycle.temp_root()

            secure.assert_not_called()
            self.assertEqual((root / "employee-data.txt").read_text(encoding="utf-8"), "keep")

    @unittest.skipUnless(os.name == "nt", "Windows ownership behavior")
    def test_foreign_owned_windows_root_is_rejected_before_acl_change(self):
        with tempfile.TemporaryDirectory() as tmp, self._managed(tmp):
            root = Path(tmp).resolve() / output_lifecycle.DEFAULT_TEMP_DIRNAME
            root.mkdir()
            with patch.object(
                output_lifecycle,
                "_verify_windows_owner",
                side_effect=ValueError("not owned by current Windows user"),
            ), patch.object(output_lifecycle, "_secure_windows_dacl") as secure:
                with self.assertRaisesRegex(ValueError, "not owned"):
                    output_lifecycle.temp_root()

            secure.assert_not_called()

    def test_cleanup_removes_only_expired_marked_jobs(self):
        with tempfile.TemporaryDirectory() as tmp, self._managed(tmp):
            old_job = output_lifecycle.create_job_dir("single")
            recent_job = output_lifecycle.create_job_dir("folder")
            old_artifact = old_job / "old.png"
            recent_artifact = recent_job / "recent.png"
            old_artifact.write_bytes(b"old")
            recent_artifact.write_bytes(b"recent")
            self._age_tree(old_job, 100)
            self._age_tree(recent_job, 9_900)
            unknown = output_lifecycle.temp_root() / "employee-project"
            unknown.mkdir()
            (unknown / "keep.png").write_bytes(b"keep")
            self._age_tree(unknown, 100)

            removed = output_lifecycle.cleanup_expired(retention_hours=1, now=10_000)

            self.assertEqual(removed, [old_job.absolute()])
            self.assertFalse(old_job.exists())
            self.assertTrue(recent_artifact.is_file())
            self.assertTrue((unknown / "keep.png").is_file())

    def test_cleanup_keeps_old_job_with_recent_artifact_activity(self):
        with tempfile.TemporaryDirectory() as tmp, self._managed(tmp):
            job = output_lifecycle.create_job_dir("folder")
            artifact = job / "latest.png"
            artifact.write_bytes(b"active")
            self._age_tree(job, 100)
            os.utime(artifact, (9_900, 9_900))

            removed = output_lifecycle.cleanup_expired(retention_hours=1, now=10_000)

            self.assertEqual(removed, [])
            self.assertTrue(artifact.is_file())

    def test_cleanup_keeps_job_while_activity_lock_is_held(self):
        with tempfile.TemporaryDirectory() as tmp, self._managed(tmp):
            job = output_lifecycle.create_job_dir("folder")
            artifact = job / "old.png"
            artifact.write_bytes(b"old")
            self._age_tree(job, 100)

            with output_lifecycle.job_activity_for_path(job):
                removed = output_lifecycle.cleanup_expired(retention_hours=1, now=10_000)

            self.assertEqual(removed, [])
            self.assertTrue(artifact.is_file())

    def test_cleanup_rechecks_activity_after_expiry_scan(self):
        with tempfile.TemporaryDirectory() as tmp, self._managed(tmp):
            job = output_lifecycle.create_job_dir("folder")
            (job / "old.png").write_bytes(b"old")
            self._age_tree(job, 100)
            original = output_lifecycle._latest_mtime
            held = []

            def activate_during_scan(path):
                context = output_lifecycle.job_activity_for_path(job)
                context.__enter__()
                held.append(context)
                return original(path)

            try:
                with patch.object(output_lifecycle, "_latest_mtime", side_effect=activate_during_scan):
                    removed = output_lifecycle.cleanup_expired(
                        retention_hours=1,
                        now=4_000_000_000,
                    )
            finally:
                for context in held:
                    context.__exit__(None, None, None)

            self.assertEqual(removed, [])
            self.assertTrue(job.is_dir())

    def test_stale_activity_lock_file_does_not_prevent_cleanup(self):
        with tempfile.TemporaryDirectory() as tmp, self._managed(tmp):
            job = output_lifecycle.create_job_dir("single")
            stale = job / f"{output_lifecycle.ACTIVE_MARKER_PREFIX}crashed.lock"
            stale.write_bytes(b"stale")
            self._age_tree(job, 100)

            removed = output_lifecycle.cleanup_expired(retention_hours=1, now=10_000)

            self.assertEqual(removed, [job.absolute()])
            self.assertFalse(job.exists())

    def test_stale_batch_lock_file_does_not_prevent_cleanup(self):
        with tempfile.TemporaryDirectory() as tmp, self._managed(tmp):
            job = output_lifecycle.create_job_dir("folder")
            output = job / "outputs"
            output.mkdir()
            (output / ".heituzimggen2-batch.lock").write_text("stale", encoding="utf-8")
            self._age_tree(job, 100)

            removed = output_lifecycle.cleanup_expired(retention_hours=1, now=10_000)

            self.assertEqual(removed, [job.absolute()])
            self.assertFalse(job.exists())

    def test_stale_cleanup_claim_is_recovered(self):
        with tempfile.TemporaryDirectory() as tmp, self._managed(tmp):
            job = output_lifecycle.create_job_dir("single")
            (job / "old.png").write_bytes(b"old")
            self._age_tree(job, 100)
            claim_id = "a" * 32
            (job / output_lifecycle.CLEANUP_MARKER_NAME).write_text(
                json.dumps({
                    "application": output_lifecycle.APPLICATION_NAME,
                    "schema": output_lifecycle.MARKER_SCHEMA,
                    "claimed_at": 100,
                    "job_id": job.name,
                    "claim_id": claim_id,
                }),
                encoding="utf-8",
            )

            removed = output_lifecycle.cleanup_expired(retention_hours=1, now=10_000)

            self.assertEqual(removed, [job.absolute()])
            self.assertFalse(job.exists())

    def test_recent_cleanup_claim_is_not_stolen(self):
        with tempfile.TemporaryDirectory() as tmp, self._managed(tmp):
            job = output_lifecycle.create_job_dir("single")
            artifact = job / "old.png"
            artifact.write_bytes(b"old")
            self._age_tree(job, 100)
            (job / output_lifecycle.CLEANUP_MARKER_NAME).write_text(
                json.dumps({
                    "application": output_lifecycle.APPLICATION_NAME,
                    "schema": output_lifecycle.MARKER_SCHEMA,
                    "claimed_at": 9_900,
                    "job_id": job.name,
                    "claim_id": "b" * 32,
                }),
                encoding="utf-8",
            )

            removed = output_lifecycle.cleanup_expired(retention_hours=1, now=10_000)

            self.assertEqual(removed, [])
            self.assertTrue(artifact.is_file())

    def test_quarantine_requires_canonical_bound_job_identity(self):
        with tempfile.TemporaryDirectory() as tmp, self._managed(tmp):
            root = output_lifecycle.temp_root()
            claim_id = "c" * 32
            quarantine = root / f"{output_lifecycle.DELETING_PREFIX}{claim_id}-victim"
            quarantine.mkdir()
            (quarantine / "keep.png").write_bytes(b"keep")
            (quarantine / output_lifecycle.JOB_MARKER_NAME).write_text(
                json.dumps({
                    "application": output_lifecycle.APPLICATION_NAME,
                    "schema": output_lifecycle.MARKER_SCHEMA,
                    "kind": "single",
                    "job_id": "victim",
                    "created_at": 100,
                }),
                encoding="utf-8",
            )
            (quarantine / output_lifecycle.CLEANUP_MARKER_NAME).write_text(
                json.dumps({
                    "application": output_lifecycle.APPLICATION_NAME,
                    "schema": output_lifecycle.MARKER_SCHEMA,
                    "claimed_at": 100,
                    "job_id": "victim",
                    "claim_id": claim_id,
                }),
                encoding="utf-8",
            )
            self._age_tree(quarantine, 100)

            removed = output_lifecycle.cleanup_expired(retention_hours=1, now=10_000)

            self.assertEqual(removed, [])
            self.assertTrue((quarantine / "keep.png").is_file())

    def test_valid_expired_quarantine_from_crash_is_removed(self):
        with tempfile.TemporaryDirectory() as tmp, self._managed(tmp):
            job = output_lifecycle.create_job_dir("folder")
            (job / "old.png").write_bytes(b"old")
            self._age_tree(job, 100)
            claim_id = "d" * 32
            (job / output_lifecycle.CLEANUP_MARKER_NAME).write_text(
                json.dumps({
                    "application": output_lifecycle.APPLICATION_NAME,
                    "schema": output_lifecycle.MARKER_SCHEMA,
                    "claimed_at": 100,
                    "job_id": job.name,
                    "claim_id": claim_id,
                }),
                encoding="utf-8",
            )
            quarantine = job.parent / f"{output_lifecycle.DELETING_PREFIX}{claim_id}-{job.name}"
            os.replace(job, quarantine)

            removed = output_lifecycle.cleanup_expired(retention_hours=1, now=10_000)

            self.assertEqual(removed, [])
            self.assertFalse(quarantine.exists())

    def test_concurrent_cleanup_process_is_serialized_by_root_lock(self):
        with tempfile.TemporaryDirectory() as tmp, self._managed(tmp):
            job = output_lifecycle.create_job_dir("single")
            (job / "old.png").write_bytes(b"old")
            self._age_tree(job, 100)
            lock = output_lifecycle.temp_root() / output_lifecycle.ROOT_CLEANUP_LOCK_NAME
            handle = lock.open("a+b")
            self.assertTrue(output_lifecycle._lock_file(handle, nonblocking=False))
            try:
                removed = output_lifecycle.cleanup_expired(retention_hours=1, now=10_000)
            finally:
                output_lifecycle._unlock_file(handle)
                handle.close()

            self.assertEqual(removed, [])
            self.assertTrue(job.exists())
            self.assertEqual(
                output_lifecycle.cleanup_expired(retention_hours=1, now=10_000),
                [job.absolute()],
            )

    def test_nonfinite_retention_and_now_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp, self._managed(tmp):
            with self.assertRaisesRegex(ValueError, "finite"):
                output_lifecycle.cleanup_expired(retention_hours=float("nan"), now=10_000)
            with self.assertRaisesRegex(ValueError, "finite"):
                output_lifecycle.cleanup_expired(retention_hours=1, now=float("inf"))
            with self.assertRaisesRegex(ValueError, "positive"):
                output_lifecycle.cleanup_expired(retention_hours=1, now=-1)
            with patch.dict(os.environ, {output_lifecycle.RETENTION_HOURS_ENV: "NaN"}):
                with self.assertRaisesRegex(ValueError, "finite"):
                    output_lifecycle.retention_hours()

    @unittest.skipUnless(os.name == "nt", "Windows junction behavior")
    def test_cleanup_does_not_traverse_junction_descendants(self):
        with tempfile.TemporaryDirectory() as tmp, self._managed(tmp):
            job = output_lifecycle.create_job_dir("folder")
            external = Path(tmp) / "external"
            external.mkdir()
            future = external / "future.txt"
            future.write_text("keep", encoding="utf-8")
            os.utime(future, (4_000_000_000, 4_000_000_000))
            junction = job / "junction"
            completed = subprocess.run(
                ["cmd.exe", "/c", "mklink", "/J", str(junction), str(external)],
                capture_output=True,
                text=True,
                errors="replace",
            )
            if completed.returncode != 0:
                self.skipTest(f"junction creation unavailable: {completed.stderr or completed.stdout}")
            for item in job.iterdir():
                if item != junction:
                    os.utime(item, (100, 100))
            os.utime(job, (100, 100))

            removed = output_lifecycle.cleanup_expired(
                retention_hours=1,
                now=4_000_000_000,
            )

            self.assertEqual(removed, [job.absolute()])
            self.assertTrue(future.is_file())

    @unittest.skipUnless(os.name == "nt", "Windows ACL behavior")
    def test_temp_root_applies_windows_private_acl(self):
        with tempfile.TemporaryDirectory() as tmp, self._managed(tmp), patch.object(
            output_lifecycle, "_secure_windows_dacl"
        ) as secure:
            root = output_lifecycle.temp_root()
            secure.assert_called_with(root)

    @unittest.skipUnless(os.name == "nt", "Windows ACL behavior")
    def test_windows_acl_is_reset_then_restricted_to_user_and_system(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "managed"
            path.mkdir()
            completed = subprocess.CompletedProcess
            responses = [
                completed([], 0, stdout=b'"host\\user","S-1-5-21-1-2-3-1001"\r\n', stderr=b""),
                completed([], 0, stdout=b"", stderr=b""),
                completed([], 0, stdout=b"", stderr=b""),
            ]
            with patch.object(output_lifecycle.subprocess, "run", side_effect=responses) as run:
                output_lifecycle._secure_windows_dacl(path)

            self.assertIn("/reset", run.call_args_list[1].args[0])
            restricted = run.call_args_list[2].args[0]
            self.assertIn("/inheritance:r", restricted)
            self.assertIn("*S-1-5-21-1-2-3-1001:(OI)(CI)F", restricted)
            self.assertIn("*S-1-5-18:(OI)(CI)F", restricted)

    def test_cleanup_preserves_unknown_symlink_and_target(self):
        with tempfile.TemporaryDirectory() as tmp, self._managed(tmp):
            root = output_lifecycle.temp_root()
            target = Path(tmp) / "employee-output"
            target.mkdir()
            (target / "keep.png").write_bytes(b"keep")
            link = root / "old-link"
            try:
                link.symlink_to(target, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"directory symlinks unavailable: {exc}")

            removed = output_lifecycle.cleanup_expired(
                retention_hours=1,
                now=1_000_000_000_000,
            )

            self.assertEqual(removed, [])
            self.assertTrue(link.is_symlink())
            self.assertTrue((target / "keep.png").is_file())

    def test_persistent_destination_inside_managed_root_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp, self._managed(tmp):
            root = output_lifecycle.temp_root()
            with self.assertRaisesRegex(ValueError, "temporary root"):
                output_lifecycle.validate_persistent_destination(root / "explicit" / "result.png")

            outside = Path(tmp) / "shared-results"
            self.assertEqual(
                output_lifecycle.validate_persistent_destination(outside),
                outside.absolute(),
            )

    def test_creating_job_does_not_cleanup_old_jobs(self):
        with tempfile.TemporaryDirectory() as tmp, self._managed(tmp):
            old_job = output_lifecycle.create_job_dir("single")
            artifact = old_job / "old.png"
            artifact.write_bytes(b"old")
            self._age_tree(old_job, 100)

            output_lifecycle.create_job_dir("single")

            self.assertTrue(artifact.is_file())


if __name__ == "__main__":
    unittest.main()
