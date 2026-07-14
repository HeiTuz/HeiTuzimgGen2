import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import creative_batch
import mpw_prompt_adapter


def write_manifest(_prompt, _style, count, output, **_kwargs):
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        for index in range(1, count + 1):
            handle.write(json.dumps({
                "id": f"variation-{index:03d}",
                "full_prompt": f"enhanced variation {index}",
                "output_path": f"images/{index:03d}.png",
                "qc_required": False,
                "metadata": {"mpw_compiled": True, "ideation_batch": count > 1},
            }) + "\n")
    return output


class MpwPromptAdapterTests(unittest.TestCase):
    def test_single_prompt_modes(self):
        self.assertEqual(mpw_prompt_adapter.compile_single_prompt("plain", mode="off"), ("plain", False))
        with mock.patch.object(mpw_prompt_adapter, "discover_mpw_root", return_value=None):
            self.assertEqual(mpw_prompt_adapter.compile_single_prompt("plain", mode="auto"), ("plain", False))
            with self.assertRaises(mpw_prompt_adapter.MpwPromptError):
                mpw_prompt_adapter.compile_single_prompt("plain", mode="required")

    def test_auto_hook_compiles_one_and_cleans_temp(self):
        with mock.patch.object(mpw_prompt_adapter, "discover_mpw_root", return_value=Path("/fake/mpw")), \
             mock.patch.object(mpw_prompt_adapter, "compile_manifest", side_effect=write_manifest):
            prompt, compiled = mpw_prompt_adapter.compile_single_prompt("plain", mode="auto")
        self.assertTrue(compiled)
        self.assertEqual(prompt, "enhanced variation 1")


class CreativeBatchTests(unittest.TestCase):
    def test_hundred_item_dry_run_is_qc_free_and_leaves_no_workspace(self):
        captured = {}
        def dry_runner(manifest, output_root, **kwargs):
            rows = [json.loads(line) for line in Path(manifest).read_text().splitlines()]
            captured["rows"] = rows
            return {"mode": "dry_run", "jobs": len(rows), "outputs": [row["output_path"] for row in rows]}
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(creative_batch, "compile_manifest", side_effect=write_manifest):
            final = Path(tmp) / "final"
            result = creative_batch.run_creative_batch("cats", "indie editorial", 100, final, batch_runner=dry_runner)
            self.assertFalse(final.exists())
            self.assertFalse(any(Path(tmp).glob(".final.heituz-work-*")))
        self.assertEqual(len(captured["rows"]), 100)
        self.assertEqual(len({row["full_prompt"] for row in captured["rows"]}), 100)
        self.assertTrue(all(row["qc_required"] is False for row in captured["rows"]))
        self.assertFalse(result["workspace_retained"])

    def test_success_publishes_only_images_and_removes_workspace(self):
        def success_runner(manifest, output_root, **kwargs):
            rows = [json.loads(line) for line in Path(manifest).read_text().splitlines()]
            for row in rows:
                path = Path(output_root) / row["output_path"]
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"\x89PNG\r\n\x1a\ncontent")
            return {"counts": {"succeeded": len(rows)}, "awaiting_qc": [], "awaiting_pilot_qc": False}
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(creative_batch, "compile_manifest", side_effect=write_manifest):
            final = Path(tmp) / "final"
            result = creative_batch.run_creative_batch("cats", "indie editorial", 3, final, execute=True, batch_runner=success_runner)
            self.assertEqual(sorted(path.name for path in final.iterdir()), ["001.png", "002.png", "003.png"])
            self.assertTrue(all(path.is_file() for path in final.iterdir()))
            self.assertFalse(any(Path(tmp).glob(".final.heituz-work-*")))
            self.assertEqual(result["count"], 3)

    def test_failure_retains_workspace_for_resume(self):
        def failed_runner(_manifest, _output_root, **_kwargs):
            return {"counts": {"succeeded": 1, "failed": 1}, "awaiting_qc": [], "awaiting_pilot_qc": False}
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(creative_batch, "compile_manifest", side_effect=write_manifest):
            final = Path(tmp) / "final"
            with self.assertRaisesRegex(creative_batch.CreativeBatchError, "workspace retained"):
                creative_batch.run_creative_batch("cats", "", 2, final, execute=True, batch_runner=failed_runner)
            workspaces = list(Path(tmp).glob(".final.heituz-work-*"))
            self.assertEqual(len(workspaces), 1)
            self.assertTrue((workspaces[0] / "variations.jsonl").is_file())
            self.assertFalse(final.exists())


if __name__ == "__main__":
    unittest.main()
