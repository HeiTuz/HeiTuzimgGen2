import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
MODULE_PATH = SCRIPTS / "codex_subscription_batch.py"
SPEC = importlib.util.spec_from_file_location("codex_subscription_batch", MODULE_PATH)
batch = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = batch
SPEC.loader.exec_module(batch)


def write_jsonl(path: Path, records):
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")


class FakeRunner:
    def __init__(self, failures=None, delay=0.0):
        self.failures = failures or {}
        self.delay = delay
        self.calls = []
        self.active = 0
        self.max_active = 0
        self.lock = threading.Lock()

    def __call__(self, prompt, output, images, execute=False, codex_bin=None, codex_provenance=None):
        with self.lock:
            self.calls.append((prompt, output, tuple(images), execute, codex_bin, codex_provenance))
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        try:
            if self.delay:
                time.sleep(self.delay)
            category = self.failures.get(prompt)
            if category:
                raise batch.transport.TransportError(f"Codex CLI failed; category={category}")
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(("png:" + prompt).encode())
            return {"transport_state": "succeeded", "source_artifact": f"/session/{prompt}.png"}
        finally:
            with self.lock:
                self.active -= 1


def raw_approved_batch(manifest, out, runner, **kwargs):
    _, digest = batch.load_manifest(manifest, out)
    approval = batch.approval_digest(
        digest, kwargs.get("workers", "auto"), kwargs.get("start", 1), kwargs.get("hard_cap", 8),
        kwargs.get("ramp_every", 3), kwargs.get("ram_per_worker_gb", 0.5),
    )
    with patch.dict(os.environ, {batch.BATCH_APPROVAL_ENV: approval}, clear=False):
        return batch.run_batch(manifest, out, execute=True, runner=runner, **kwargs)


def complete_approved_batch(manifest, out, runner, **kwargs):
    summary = raw_approved_batch(manifest, out, runner, **kwargs)
    if summary.get("awaiting_pilot_qc"):
        jobs, _ = batch.load_manifest(manifest, out)
        pilot = next(job for job in jobs if job.id == summary["pilot_id"])
        qc_record = {
            "id": pilot.id,
            "axis_scores": {"goal_fit": 5, "text_accuracy": 5, "material_realism": 5, "layout": 5},
            "rendered_text_exists": pilot.rendered_text_exists,
        }
        if pilot.promotional:
            qc_record["promo"] = {
                "physical_type_subject_interaction": True,
                "generic_card_regression": False,
                "printed_meta_ui_not_literal": True,
                "color_count": 3,
                "finishing_device_count": 2,
                "korean_glyph_mask_safe": True,
            }
        qc_path = Path(manifest).parent / f".{Path(manifest).stem}-pilot-qc.jsonl"
        write_jsonl(qc_path, [qc_record])
        batch.reconcile_qc(manifest, out, qc_path, ledger_path=kwargs.get("ledger_path"))
        summary = raw_approved_batch(manifest, out, runner, **kwargs)
    return summary


class BatchManifestTests(unittest.TestCase):
    def test_manifest_validates_and_hash_is_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ref = root / "ref.png"; ref.write_bytes(b"ref")
            manifest = root / "jobs.jsonl"
            records = [
                {"id": "a", "prompt": "one", "output_path": "a.png", "images": ["ref.png"]},
                {"id": "b", "prompt": "two", "output_path": "nested/b.png", "series_locks": {"palette": "red"}},
            ]
            write_jsonl(manifest, records)
            jobs1, hash1 = batch.load_manifest(manifest, root / "out")
            jobs2, hash2 = batch.load_manifest(manifest, root / "out")
            self.assertEqual(hash1, hash2)
            self.assertEqual([j.id for j in jobs1], ["a", "b"])
            self.assertEqual(jobs1[0].images, (ref.resolve(),))
            self.assertEqual(jobs1[1].metadata["series_locks"], {"palette": "red"})
            self.assertEqual(jobs1[0].metadata["reference_evidence"][0]["sha256"], batch.file_digest(ref)[0])
            ref.write_bytes(b"changed-reference")
            _, changed_hash = batch.load_manifest(manifest, root / "out")
            self.assertNotEqual(hash1, changed_hash)

    def test_duplicate_ids_and_outputs_are_rejected(self):
        cases = [
            [
                {"id": "a", "prompt": "one", "output_path": "a.png"},
                {"id": "a", "prompt": "two", "output_path": "b.png"},
            ],
            [
                {"id": "a", "prompt": "one", "output_path": "same.png"},
                {"id": "b", "prompt": "two", "output_path": "same.png"},
            ],
        ]
        for records in cases:
            with self.subTest(records=records), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp); manifest = root / "jobs.jsonl"; write_jsonl(manifest, records)
                with self.assertRaises(batch.BatchError):
                    batch.load_manifest(manifest, root / "out")

    def test_output_traversal_and_absolute_are_rejected(self):
        absolute_output = str(Path(tempfile.gettempdir()) / "absolute.png")
        for output in ("../escape.png", absolute_output):
            with self.subTest(output=output), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp); manifest = root / "jobs.jsonl"
                write_jsonl(manifest, [{"id": "a", "prompt": "one", "output_path": output}])
                with self.assertRaises(batch.BatchError):
                    batch.load_manifest(manifest, root / "out")

    def test_mpw_full_prompt_and_non_png_output_are_normalized(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); manifest = root / "jobs.jsonl"
            write_jsonl(manifest, [{
                "id": "PROMO-P1", "category": "C3", "cut_type": "promo_poster",
                "full_prompt": "Scene: poster. Text-in-image: headline \\\"여름\\\". AR 4:5",
                "output_path": "out/promo.webp", "output_format": "webp",
                "korean_copy": "여름", "ar": "4:5", "size": "1024x1536", "quality": "high",
                "promo_pattern": "P1", "look_preset": "L1", "promo_text_effect": "mask",
                "promo_subject": "바다", "finishing_devices": ["barcode"],
                "palette_authority": "P", "palette_sources": ["P"], "palette": ["#111111", "#eeeeee"],
            }])
            jobs, _ = batch.load_manifest(manifest, root / "outputs")
            self.assertEqual(jobs[0].output_path, "out/promo.png")
            self.assertTrue(jobs[0].promotional)
            self.assertTrue(jobs[0].rendered_text_exists)
            self.assertEqual(jobs[0].metadata["compiled_output_path"], "out/promo.webp")
            self.assertNotIn("full_prompt", jobs[0].source_record)
            self.assertIn("Text-in-image", jobs[0].prompt)

    def test_symlink_parent_and_reference_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); out = root / "out"; out.mkdir()
            outside = root / "outside"; outside.mkdir()
            (out / "link").symlink_to(outside, target_is_directory=True)
            manifest = root / "jobs.jsonl"
            write_jsonl(manifest, [{"id": "a", "prompt": "one", "output_path": "link/a.png"}])
            with self.assertRaises(batch.BatchError):
                batch.load_manifest(manifest, out)
            real = root / "real.png"; real.write_bytes(b"x")
            ref = root / "ref.png"; ref.symlink_to(real)
            write_jsonl(manifest, [{"id": "a", "prompt": "one", "output_path": "a.png", "images": ["ref.png"]}])
            with self.assertRaises(batch.BatchError):
                batch.load_manifest(manifest, out)

    def test_more_than_four_references_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); refs = []
            for i in range(5):
                p = root / f"{i}.png"; p.write_bytes(b"x"); refs.append(p.name)
            manifest = root / "jobs.jsonl"
            write_jsonl(manifest, [{"id": "a", "prompt": "one", "output_path": "a.png", "images": refs}])
            with self.assertRaisesRegex(batch.BatchError, "four"):
                batch.load_manifest(manifest, root / "out")


class BatchExecutionTests(unittest.TestCase):
    def setUp(self):
        self.resolver_patch = patch.object(
            batch.transport,
            "resolve_codex_command",
            return_value=SimpleNamespace(
                command="/opt/codex",
                source="explicit",
                version=(0, 144, 3),
                provenance={"path": "/opt/codex", "source": "explicit", "version": [0, 144, 3]},
            ),
        )
        self.resolver_patch.start()
        self.addCleanup(self.resolver_patch.stop)
    def make_manifest(self, root, count=3):
        manifest = root / "jobs.jsonl"
        records = [{"id": f"j{i}", "prompt": f"p{i}", "output_path": f"{i}.png"} for i in range(count)]
        write_jsonl(manifest, records)
        return manifest, records

    def raw_approved_run(self, manifest, out, runner, **kwargs):
        return raw_approved_batch(manifest, out, runner, **kwargs)

    def approved_run(self, manifest, out, runner, **kwargs):
        summary = self.raw_approved_run(manifest, out, runner, **kwargs)
        if summary.get("awaiting_pilot_qc"):
            jobs, _ = batch.load_manifest(manifest, out)
            pilot = next(job for job in jobs if job.id == summary["pilot_id"])
            qc_record = {
                "id": pilot.id,
                "axis_scores": {"goal_fit": 5, "text_accuracy": 5, "material_realism": 5, "layout": 5},
                "rendered_text_exists": pilot.rendered_text_exists,
            }
            if pilot.promotional:
                qc_record["promo"] = {
                    "physical_type_subject_interaction": True,
                    "generic_card_regression": False,
                    "printed_meta_ui_not_literal": True,
                    "color_count": 3,
                    "finishing_device_count": 2,
                    "korean_glyph_mask_safe": True,
                }
            qc_path = Path(manifest).parent / f".{Path(manifest).stem}-pilot-qc.jsonl"
            write_jsonl(qc_path, [qc_record])
            batch.reconcile_qc(manifest, out, qc_path, ledger_path=kwargs.get("ledger_path"))
            summary = self.raw_approved_run(manifest, out, runner, **kwargs)
        return summary

    def test_dry_run_does_not_call_transport_or_create_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); manifest, _ = self.make_manifest(root)
            runner = FakeRunner()
            result = batch.run_batch(manifest, root / "out", runner=runner)
            self.assertEqual(result["mode"], "dry_run")
            self.assertEqual(result["pilot_id"], "j0")
            self.assertEqual(
                result["codex_provenance"],
                {"path": "/opt/codex", "source": "explicit", "version": [0, 144, 3]},
            )
            self.assertEqual(runner.calls, [])
            self.assertFalse((root / "out").exists())
            with self.assertRaisesRegex(batch.BatchError, "hard_cap=2"):
                batch.run_batch(manifest, root / "out", workers="3", hard_cap=2)

    def test_live_requires_manifest_bound_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); manifest, _ = self.make_manifest(root, 1)
            with patch.dict(os.environ, {batch.BATCH_APPROVAL_ENV: "wrong"}, clear=False):
                with self.assertRaisesRegex(batch.BatchError, "exact approval"):
                    batch.run_batch(manifest, root / "out", execute=True, runner=FakeRunner())

    def test_pilot_failure_stops_fanout(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); manifest, _ = self.make_manifest(root)
            runner = FakeRunner({"p0": "rate_limited"})
            summary = self.approved_run(manifest, root / "out", runner, workers="3")
            self.assertTrue(summary["pilot_failed"])
            self.assertEqual([c[0] for c in runner.calls], ["p0"])
            self.assertEqual(runner.calls[0][4], "/opt/codex")
            ledger = batch.load_ledger(root / "out" / batch.LEDGER_NAME)
            self.assertEqual(ledger["jobs"]["j0"]["status"], "failed")
            self.assertEqual(ledger["jobs"]["j1"]["status"], "pending")
            with self.assertRaisesRegex(batch.BatchError, "unresolved failures"):
                self.approved_run(manifest, root / "out", FakeRunner(), workers="3")
            jobs, _ = batch.load_manifest(manifest, root / "out")
            retry = root / "pilot-retry.jsonl"
            self.assertEqual(batch.write_retry_manifest(jobs, ledger, retry), 3)
            rows = [json.loads(line) for line in retry.read_text().splitlines()]
            self.assertEqual([row["id"] for row in rows], ["j0", "j1", "j2"])
            retry_ledger = root / "out" / ".pilot-retry-ledger.json"
            retried = self.approved_run(retry, root / "out", FakeRunner(), workers="3", ledger_path=retry_ledger)
            self.assertEqual(retried["counts"]["succeeded"], 3)

    def test_pilot_qc_failure_blocks_fanout_and_carries_pending_into_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); manifest, _ = self.make_manifest(root, 3); out = root / "out"
            runner = FakeRunner()
            first = self.raw_approved_run(manifest, out, runner, workers="3")
            self.assertTrue(first["awaiting_pilot_qc"])
            qc = root / "pilot-fail-qc.jsonl"
            write_jsonl(qc, [{"id": "j0", "axis_scores": {"goal_fit": 0, "text_accuracy": 5, "material_realism": 5, "layout": 5}}])
            retry = root / "pilot-qc-retry.jsonl"
            summary = batch.reconcile_qc(manifest, out, qc, retry)
            self.assertEqual(summary["counts"]["qc_failed"], 1)
            self.assertEqual(summary["counts"]["pending"], 2)
            self.assertFalse(summary["awaiting_pilot_qc"])
            self.assertEqual([json.loads(line)["id"] for line in retry.read_text().splitlines()], ["j0", "j1", "j2"])
            self.assertEqual([call[0] for call in runner.calls], ["p0"])
            with self.assertRaisesRegex(batch.BatchError, "unresolved failures"):
                self.raw_approved_run(manifest, out, runner, workers="3")

    def test_pilot_qc_gate_then_bounded_parallel_fanout_and_deterministic_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); manifest, _ = self.make_manifest(root, 6)
            runner = FakeRunner(delay=0.02)
            first = self.raw_approved_run(manifest, root / "out", runner, workers="3", start=2, hard_cap=3, ramp_every=1)
            self.assertTrue(first["awaiting_pilot_qc"])
            self.assertEqual(first["counts"]["succeeded"], 1)
            self.assertEqual(first["counts"]["pending"], 5)
            self.assertEqual([call[0] for call in runner.calls], ["p0"])
            waiting = self.raw_approved_run(manifest, root / "out", runner, workers="3", start=2, hard_cap=3, ramp_every=1)
            self.assertTrue(waiting["awaiting_pilot_qc"])
            self.assertEqual([call[0] for call in runner.calls], ["p0"])
            qc = root / "pilot-qc.jsonl"
            write_jsonl(qc, [{"id": "j0", "axis_scores": {"goal_fit": 5, "text_accuracy": 5, "material_realism": 5, "layout": 5}}])
            batch.reconcile_qc(manifest, root / "out", qc)
            summary = self.raw_approved_run(manifest, root / "out", runner, workers="3", start=2, hard_cap=3, ramp_every=1)
            self.assertFalse(summary["awaiting_pilot_qc"])
            self.assertEqual(summary["counts"]["succeeded"], 6)
            self.assertLessEqual(runner.max_active, 3)
            self.assertEqual([item["id"] for item in summary["items"]], [f"j{i}" for i in range(6)])
            self.assertEqual(runner.calls[0][0], "p0")
            self.assertTrue((root / "out" / batch.SUMMARY_MD_NAME).is_file())

    def test_partial_failure_is_recorded_and_retry_manifest_contains_only_failed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); manifest, _ = self.make_manifest(root, 4)
            runner = FakeRunner({"p2": "timeout"})
            summary = self.approved_run(manifest, root / "out", runner, workers="2")
            self.assertEqual(summary["counts"]["failed"], 1)
            jobs, _ = batch.load_manifest(manifest, root / "out")
            ledger = batch.load_ledger(root / "out" / batch.LEDGER_NAME)
            retry = root / "retry.jsonl"
            self.assertEqual(batch.write_retry_manifest(jobs, ledger, retry), 1)
            rows = [json.loads(line) for line in retry.read_text().splitlines()]
            self.assertEqual([row["id"] for row in rows], ["j2"])
            self.assertEqual(rows[0]["retry_of"], "j2")

    def test_resume_skips_only_hash_verified_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); manifest, _ = self.make_manifest(root, 2)
            first = FakeRunner(); self.approved_run(manifest, root / "out", first, workers="2")
            second = FakeRunner(); summary = self.approved_run(manifest, root / "out", second, workers="2")
            self.assertEqual(second.calls, [])
            self.assertEqual(summary["counts"]["succeeded"], 2)
            with self.assertRaisesRegex(batch.BatchError, "Execution config drift"):
                self.raw_approved_run(manifest, root / "out", FakeRunner(), workers="1")
            (root / "out" / "1.png").write_bytes(b"tampered")
            with self.assertRaisesRegex(batch.BatchError, "hash/size"):
                self.approved_run(manifest, root / "out", FakeRunner(), workers="2")

    def test_unowned_existing_output_is_conflict(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); manifest, _ = self.make_manifest(root, 1); out = root / "out"; out.mkdir()
            (out / "0.png").write_bytes(b"preexisting")
            with self.assertRaisesRegex(batch.BatchError, "conflicts"):
                self.approved_run(manifest, out, FakeRunner())

    def test_interrupted_running_is_recovered_to_pending(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); manifest, _ = self.make_manifest(root, 1); out = root / "out"; out.mkdir()
            jobs, digest = batch.load_manifest(manifest, out)
            approval = batch.approval_digest(digest, "auto", 1, 8, 3, 0.5)
            ledger = batch.new_ledger(jobs, digest, {
                "workers": "auto", "start": 1, "hard_cap": 8,
                "ramp_every": 3, "ram_per_worker_gb": 0.5,
                "approval_sha256": approval,
                "codex_provenance": {
                    "path": "/opt/codex",
                    "source": "explicit",
                    "version": [0, 144, 3],
                },
            })
            ledger["jobs"]["j0"]["status"] = "running"
            batch.atomic_write_json(out / batch.LEDGER_NAME, ledger)
            summary = self.approved_run(manifest, out, FakeRunner())
            self.assertEqual(summary["counts"]["succeeded"], 1)
            recovered = batch.load_ledger(out / batch.LEDGER_NAME)
            self.assertEqual(len(recovered["jobs"]["j0"]["attempts"]), 1)

    def test_corrupt_ledger_and_manifest_drift_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); manifest, records = self.make_manifest(root, 1); out = root / "out"; out.mkdir()
            (out / batch.LEDGER_NAME).write_text("not-json")
            with self.assertRaisesRegex(batch.BatchError, "corrupt"):
                self.approved_run(manifest, out, FakeRunner())
            (out / batch.LEDGER_NAME).unlink()
            self.approved_run(manifest, out, FakeRunner())
            records[0]["prompt"] = "changed"; write_jsonl(manifest, records)
            _, changed_hash = batch.load_manifest(manifest, out)
            changed_approval = batch.approval_digest(changed_hash, "auto", 1, 8, 3, 0.5)
            with patch.dict(os.environ, {batch.BATCH_APPROVAL_ENV: changed_approval}, clear=False):
                with self.assertRaisesRegex(batch.BatchError, "Manifest drift"):
                    batch.run_batch(manifest, out, execute=True, runner=FakeRunner())

    def test_output_root_lock_rejects_concurrent_owner(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with batch.batch_lock(root):
                with self.assertRaisesRegex(batch.BatchError, "Another batch runner"):
                    with batch.batch_lock(root):
                        pass
            self.assertTrue((root / batch.LOCK_NAME).is_file())

    def test_rate_limit_freezes_adaptive_growth(self):
        limiter = batch.AdaptiveLimiter(target=4, start=1, ramp_every=1)
        limiter.success(); self.assertEqual(limiter.permits, 2)
        limiter.throttle(); limiter.success(); limiter.success()
        self.assertEqual(limiter.permits, 2)
        self.assertTrue(limiter.throttled)


class BatchQcTests(unittest.TestCase):
    def setUp(self):
        self.resolver_patch = patch.object(
            batch.transport,
            "resolve_codex_command",
            return_value=SimpleNamespace(
                command="/opt/codex",
                source="explicit",
                version=(0, 144, 3),
                provenance={"path": "/opt/codex", "source": "explicit", "version": [0, 144, 3]},
            ),
        )
        self.resolver_patch.start()
        self.addCleanup(self.resolver_patch.stop)
    def test_qc_marks_only_failed_cut_and_builds_delta_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); manifest = root / "jobs.jsonl"; out = root / "out"
            write_jsonl(manifest, [
                {"id": "good", "prompt": "good prompt", "output_path": "good.png", "rendered_text_exists": True},
                {"id": "bad", "prompt": "bad prompt", "output_path": "bad.png", "rendered_text_exists": True, "metadata": {"series": "locked"}},
            ])
            complete_approved_batch(manifest, out, FakeRunner(), workers="2")
            qc = root / "qc.jsonl"
            write_jsonl(qc, [
                {"id": "good", "axis_scores": {"goal_fit": 5, "text_accuracy": 5, "material_realism": 4, "layout": 4}},
                {"id": "bad", "axis_scores": {"goal_fit": 5, "text_accuracy": 2, "material_realism": 5, "layout": 5}},
            ])
            retry = root / "retry.jsonl"
            summary = batch.reconcile_qc(manifest, out, qc, retry)
            self.assertEqual(summary["counts"]["qc_failed"], 1)
            rows = [json.loads(line) for line in retry.read_text().splitlines()]
            self.assertEqual([row["id"] for row in rows], ["bad"])
            self.assertIn("Specify each copy string verbatim", rows[0]["prompt"])
            self.assertTrue(rows[0]["output_path"].startswith("retries/"))
            self.assertEqual(rows[0]["metadata"]["series"], "locked")
            self.assertEqual(rows[0]["metadata"]["reference_evidence"], [])

    def test_retry_manifest_runs_in_same_output_root_with_separate_ledger(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); manifest = root / "jobs.jsonl"; out = root / "out"
            write_jsonl(manifest, [{"id": "cut", "prompt": "original", "output_path": "cut.png", "rendered_text_exists": True}])
            complete_approved_batch(manifest, out, FakeRunner())
            original_bytes = (out / "cut.png").read_bytes()
            qc = root / "qc.jsonl"
            write_jsonl(qc, [{"id": "cut", "axis_scores": {"goal_fit": 5, "text_accuracy": 2, "material_realism": 5, "layout": 5}}])
            retry = root / "retry.jsonl"
            batch.reconcile_qc(manifest, out, qc, retry)
            retry_ledger = out / ".heituzimggen2-retry.json"
            summary = complete_approved_batch(retry, out, FakeRunner(), ledger_path=retry_ledger)
            self.assertEqual(summary["counts"]["succeeded"], 1)
            self.assertEqual((out / "cut.png").read_bytes(), original_bytes)
            self.assertTrue((out / "retries" / "cut-attempt-2.png").is_file())
            self.assertTrue(retry_ledger.is_file())
            self.assertTrue((out / "heituzimggen2-retry-summary.json").is_file())
            self.assertTrue((out / batch.SUMMARY_JSON_NAME).is_file())
            qc_again = root / "qc-again.jsonl"
            write_jsonl(qc_again, [{"id": "cut", "axis_scores": {"goal_fit": 5, "text_accuracy": 3, "material_realism": 5, "layout": 5}}])
            retry_again = root / "retry-again.jsonl"
            batch.reconcile_qc(retry, out, qc_again, retry_again, ledger_path=retry_ledger)
            retry_again_row = json.loads(retry_again.read_text().strip())
            self.assertEqual(retry_again_row["output_path"], "retries/cut-attempt-3.png")
            self.assertEqual(retry_again_row["retry_generation"], 2)

    def test_promotional_qc_is_mandatory_and_selective(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); manifest = root / "jobs.jsonl"; out = root / "out"
            write_jsonl(manifest, [{"id": "promo", "prompt": "poster", "output_path": "promo.png", "promotional": True}])
            complete_approved_batch(manifest, out, FakeRunner())
            qc = root / "qc.jsonl"
            write_jsonl(qc, [{"id": "promo", "axis_scores": {"goal_fit": 5, "text_accuracy": 5, "material_realism": 5, "layout": 5}}])
            with self.assertRaisesRegex(batch.BatchError, "requires promo QC"):
                batch.reconcile_qc(manifest, out, qc)
            write_jsonl(qc, [{
                "id": "promo", "axis_scores": {"goal_fit": 5, "text_accuracy": 5, "material_realism": 5, "layout": 5},
                "promo": {"physical_type_subject_interaction": False, "generic_card_regression": False, "printed_meta_ui_not_literal": True, "color_count": 3, "finishing_device_count": 2, "korean_glyph_mask_safe": True},
            }])
            retry = root / "retry.jsonl"
            summary = batch.reconcile_qc(manifest, out, qc, retry)
            self.assertEqual(summary["counts"]["qc_failed"], 1)
            self.assertIn("physical_type_subject_interaction", retry.read_text())


if __name__ == "__main__":
    unittest.main()
