import copy
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_DIR.parent
MPW_ROOT = Path(os.environ["HEITUZ_MPW_ROOT"]).expanduser() if os.environ.get("HEITUZ_MPW_ROOT") else None


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


fullset = load("apparel_three_fullset_test", SCRIPT_DIR / "apparel_three_fullset.py")
browser_task = load("browser_gpt_apparel_task_test", SCRIPT_DIR / "browser_gpt_apparel_task.py")
mpw_compiler = load("mpw_apparel_handoff_test", MPW_ROOT / "scripts" / "compile_apparel_handoff.py") if MPW_ROOT else None


class ApparelDynamicFullSetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.source = self.root / "source"
        self.source.mkdir()
        for name in ("front-a.png", "back-a.png", "detail-a.png", "front-b.png", "front-c.png", "front-d.png"):
            (self.source / name).write_bytes(name.encode())
        self.outputs = [
            {"id": "front-a", "filename": "front-a.png", "prompt": "IMAGE. front A"},
            {"id": "front-b", "filename": "front-b.png", "prompt": "IMAGE. front B"},
            {"id": "main-back", "filename": "main-back.png", "prompt": "IMAGE. main back"},
        ]
        self.run_root = self.root / "runs"

    def tearDown(self):
        self.tmp.cleanup()

    def contract(self, colors=("navy", "ivory", "red", "black")):
        role_map = [
            {"file": "front-a.png", "role": "color_front", "color_identity": colors[0]},
            {"file": "back-a.png", "role": "main_back", "color_identity": colors[0]},
            {"file": "detail-a.png", "role": "fabric_detail", "color_identity": colors[0]},
        ]
        for index, color in enumerate(colors[1:], start=1):
            role_map.append({"file": f"front-{chr(ord('a') + index)}.png", "role": "color_front", "color_identity": color})
        return {
            "schema_version": 1,
            "folder_id": "sku-001",
            "source_folder": str(self.source),
            "sources": [path.name for path in sorted(self.source.iterdir())],
            "vision_role_map": role_map,
            "normalized_color_identity": list(colors),
            "unique_color_count": len(colors),
            "heituzmpw_folder_master": "same immutable folder master",
            "qc_contract": "source fidelity, support removal, pure white, no invention, family similarity",
            "outputs": self.outputs,
        }

    def prepare(self, colors=("navy", "ivory", "red", "black")):
        contract = self.contract(colors)
        contract["folder_id"] = f"sku-{len(colors)}"
        contract_path = self.root / f"contract-{len(colors)}.json"
        contract_path.write_text(json.dumps(contract), encoding="utf-8")
        return fullset.prepare_folder(contract_path, self.run_root)

    def populate_candidates(self, coordinator, missing=None):
        folder_root = Path(coordinator["folder_root"])
        shared = fullset.read_json(folder_root / "shared-folder-contract.json")
        missing = missing or set()
        for task_number, set_name in enumerate(coordinator["candidate_sets"], start=1):
            rows = {}
            for output in self.outputs:
                path = folder_root / set_name / output["filename"]
                if (set_name, output["id"]) in missing:
                    continue
                path.write_bytes(f"{set_name}:{output['id']}".encode())
                rows[output["id"]] = {
                    "state": "completed",
                    "filename": output["filename"],
                    "sha256": fullset.sha256_file(path),
                    "size": path.stat().st_size,
                }
            ledger = {
                "schema_version": 1,
                "task_id": f"task-{task_number}",
                "candidate_set": set_name,
                "shared_contract_sha256": coordinator["shared_contract_sha256"],
                "outputs": rows,
                "state": "complete" if len(rows) == len(self.outputs) else "partial",
                "identical_output_inventory": [output["filename"] for output in self.outputs],
            }
            (folder_root / set_name / "task-ledger.json").write_text(json.dumps(ledger), encoding="utf-8")

    def report(self, coordinator, preferred=None, similarity=0.90, omit_assessments=None):
        preferred = preferred or {}
        omit_assessments = omit_assessments or set()
        sets = coordinator["candidate_sets"]
        report = {"shared_contract_sha256": coordinator["shared_contract_sha256"], "outputs": {}, "similarities": []}
        for output in self.outputs:
            candidates = {}
            for set_name in sets:
                if (set_name, output["id"]) not in omit_assessments:
                    candidates[set_name] = {
                        "source_fidelity": 0.99 if preferred.get(output["id"]) == set_name else 0.80,
                        "support_removal": True,
                        "pure_white_no_shadow": True,
                        "no_invented_detail": True,
                        "vision_verdict": f"accept {set_name} {output['id']}",
                    }
            report["outputs"][output["id"]] = {"candidates": candidates}
        for i, first in enumerate(self.outputs):
            for second in self.outputs[i + 1:]:
                for first_set in sets:
                    for second_set in sets:
                        report["similarities"].append({
                            "a_output": first["id"], "a_set": first_set,
                            "b_output": second["id"], "b_set": second_set,
                            "score": similarity,
                        })
        path = Path(coordinator["folder_root"]) / "vision-selector-report.json"
        path.write_text(json.dumps(report), encoding="utf-8")
        return path

    def test_zero_one_and_four_color_task_count(self):
        zero = self.contract(("navy",))
        zero["vision_role_map"] = [{"file": "front-a.png", "role": "detail", "color_identity": "navy"}]
        zero["normalized_color_identity"] = []
        zero["unique_color_count"] = 0
        with self.assertRaisesRegex(fullset.ContractError, "blocked"):
            fullset.validate_folder_contract(zero)
        one = self.prepare(("navy",))
        four = self.prepare(("navy", "ivory", "red", "black"))
        self.assertEqual((one["task_count"], one["candidate_sets"]), (1, ["candidate-set-1"]))
        self.assertEqual((four["task_count"], four["candidate_sets"]), (4, [f"candidate-set-{n}" for n in range(1, 5)]))

    def test_duplicate_colors_and_filename_do_not_change_count(self):
        contract = self.contract(("navy", "ivory"))
        contract["vision_role_map"].extend([
            {"file": "back-a.png", "role": "color_front", "color_identity": "ＮＡＶＹ\u00a0 BLUE"},
            {"file": "detail-a.png", "role": "fabric_detail", "color_identity": "red"},
        ])
        contract["vision_role_map"][0]["color_identity"] = "navy blue"
        contract["normalized_color_identity"] = ["navy blue", "ivory"]
        contract["unique_color_count"] = 2
        normalized = fullset.validate_folder_contract(contract)
        self.assertEqual(normalized["color_identities"], ["navy blue", "ivory"])
        no_identity = copy.deepcopy(contract)
        del no_identity["vision_role_map"][0]["color_identity"]
        with self.assertRaisesRegex(fullset.ContractError, "cannot be inferred from filenames|requires"):
            fullset.validate_folder_contract(no_identity)

    def test_dynamic_tasks_share_complete_inventory_and_disjoint_paths(self):
        coordinator = self.prepare()
        specs = [fullset.read_json(Path(path)) for path in coordinator["task_specs"]]
        self.assertEqual(len(specs), 4)
        self.assertEqual([spec["task_id"] for spec in specs], [f"task-{n}" for n in range(1, 5)])
        self.assertEqual(len({spec["candidate_root"] for spec in specs}), 4)
        dry_runs = [browser_task.dry_run(Path(path)) for path in coordinator["task_specs"]]
        inventories = [[row["filename"] for row in result["complete_output_inventory"]] for result in dry_runs]
        self.assertTrue(all(inventory == inventories[0] for inventory in inventories))
        self.assertEqual(inventories[0], [output["filename"] for output in self.outputs])
        self.assertTrue(all(result["source_count"] == len(self.contract()["sources"]) for result in dry_runs))
        self.assertTrue(all(result["invariants"]["all_sources_uploaded_together"] for result in dry_runs))

    def test_runtime_20_packs_five_four_task_folders_and_blocks_oversize(self):
        base = self.prepare()
        coords = []
        for index in range(6):
            clone = dict(base)
            clone["folder_id"] = f"sku-{index}"
            clone["folder_root"] = f"/tmp/sku-{index}"
            clone["task_specs"] = [f"/tmp/sku-{index}-task-{task}.json" for task in range(1, 5)]
            coords.append(clone)
        waves = fullset.build_schedule(coords, 20)
        self.assertEqual([wave["active_count"] for wave in waves], [20, 5, 4, 1])
        oversize = dict(base)
        oversize["task_count"] = 21
        oversize["candidate_sets"] = [f"candidate-set-{n}" for n in range(1, 22)]
        oversize["task_specs"] = [f"/tmp/task-{n}.json" for n in range(1, 22)]
        with self.assertRaisesRegex(fullset.ContractError, "blocked"):
            fullset.build_schedule([oversize], 20)

    def test_dynamic_cross_set_selection_gate_missing_resume_and_provenance(self):
        coordinator = self.prepare()
        self.populate_candidates(coordinator)
        preferred = {"front-a": "candidate-set-1", "front-b": "candidate-set-2", "main-back": "candidate-set-4"}
        report = self.report(coordinator, preferred=preferred)
        coordinator_path = Path(coordinator["folder_root"]) / "coordinator.json"
        result = fullset.select_candidates(coordinator_path, report)
        selected = {row["output_id"]: row["source_candidate_set"] for row in result["files"]}
        self.assertEqual(selected, preferred)
        for row in result["files"]:
            self.assertEqual(len(row["rejected_alternatives"]), 3)
            self.assertIn("source_task", row)
            self.assertIn("source_path", row)
            self.assertIn("source_sha256", row)
        resumed = fullset.select_candidates(coordinator_path, report)
        self.assertTrue(resumed["resume_verified"])
        target = Path(coordinator["selected_root"]) / "front-a.png"
        target.write_bytes(b"tampered")
        with self.assertRaisesRegex(fullset.ContractError, "resume verification"):
            fullset.select_candidates(coordinator_path, report)

    def test_80_percent_gate_and_unowned_selected_directory_fail_closed(self):
        coordinator = self.prepare()
        self.populate_candidates(coordinator)
        path = self.report(coordinator, similarity=0.79)
        with self.assertRaisesRegex(fullset.ContractError, "80%"):
            fullset.select_candidates(Path(coordinator["folder_root"]) / "coordinator.json", path)
        self.assertFalse(Path(coordinator["selected_root"]).exists())
        selected = Path(coordinator["selected_root"])
        selected.mkdir()
        with self.assertRaisesRegex(fullset.ContractError, "without provenance"):
            fullset.select_candidates(Path(coordinator["folder_root"]) / "coordinator.json", path)

    def test_complete_inventory_immutable_sources_and_bound_candidate_roots(self):
        missing = self.contract(("navy",))
        missing["sources"].remove("detail-a.png")
        with self.assertRaisesRegex(fullset.ContractError, "complete source image inventory"):
            fullset.validate_folder_contract(missing)
        unknown_role_source = self.contract(("navy",))
        unknown_role_source["vision_role_map"].append({"file": "not-in-inventory.png", "role": "detail"})
        with self.assertRaisesRegex(fullset.ContractError, "not in complete source inventory"):
            fullset.validate_folder_contract(unknown_role_source)

        coordinator = self.prepare(("navy",))
        spec_path = Path(coordinator["task_specs"][0])
        (self.source / "front-a.png").write_bytes(b"changed after prepare")
        with self.assertRaisesRegex(browser_task.BrowserTaskError, "immutable shared source inventory changed"):
            browser_task.dry_run(spec_path)

        fresh_contract = self.contract(("ivory",))
        fresh_contract["folder_id"] = "sku-fresh"
        fresh_contract_path = self.root / "fresh-contract.json"
        fresh_contract_path.write_text(json.dumps(fresh_contract), encoding="utf-8")
        fresh = fullset.prepare_folder(fresh_contract_path, self.run_root)
        fresh_spec_path = Path(fresh["task_specs"][0])
        spec = fullset.read_json(fresh_spec_path)
        spec["candidate_root"] = str(self.root / "outside" / spec["candidate_set"])
        external_spec_path = self.root / "external-task.json"
        external_spec_path.write_text(json.dumps(spec), encoding="utf-8")
        with self.assertRaisesRegex(browser_task.BrowserTaskError, "disjoint set ownership"):
            browser_task.dry_run(external_spec_path)

    def test_source_overlap_and_candidate_ledger_provenance_fail_closed(self):
        overlap = self.contract(("navy",))
        overlap["folder_id"] = self.source.name
        overlap_path = self.root / "overlap-contract.json"
        overlap_path.write_text(json.dumps(overlap), encoding="utf-8")
        with self.assertRaisesRegex(fullset.ContractError, "overlaps read-only source"):
            fullset.prepare_folder(overlap_path, self.root)

        no_ledger = self.prepare(("navy", "ivory"))
        self.populate_candidates(no_ledger)
        no_ledger_report = self.report(no_ledger)
        (Path(no_ledger["folder_root"]) / "candidate-set-1" / "task-ledger.json").unlink()
        with self.assertRaisesRegex(fullset.ContractError, "ledger missing"):
            fullset.select_candidates(Path(no_ledger["folder_root"]) / "coordinator.json", no_ledger_report)

        tampered = self.prepare(("navy", "ivory", "red"))
        self.populate_candidates(tampered)
        tampered_report = self.report(tampered)
        (Path(tampered["folder_root"]) / "candidate-set-1" / "front-a.png").write_bytes(b"forged")
        with self.assertRaisesRegex(fullset.ContractError, "not ledger-verified"):
            fullset.select_candidates(Path(tampered["folder_root"]) / "coordinator.json", tampered_report)

        incomplete = self.prepare(("navy", "ivory", "red", "black"))
        self.populate_candidates(incomplete, missing={("candidate-set-1", "front-a")})
        incomplete_report = self.report(incomplete)
        with self.assertRaisesRegex(fullset.ContractError, "ledger identity|ledger inventory"):
            fullset.select_candidates(Path(incomplete["folder_root"]) / "coordinator.json", incomplete_report)

    def test_portable_producer_to_consumer_handoff_is_network_free(self):
        if MPW_ROOT is None or mpw_compiler is None:
            self.skipTest("set HEITUZ_MPW_ROOT to run cross-skill handoff integration")
        self.assertEqual(
            (SKILL_ROOT / "references" / "apparel-handoff.schema.json").read_bytes(),
            (MPW_ROOT / "contracts" / "v1" / "apparel-handoff.schema.json").read_bytes(),
        )
        self.assertEqual(
            (SKILL_ROOT / "references" / "fixtures" / "apparel-handoff.valid.json").read_bytes(),
            (MPW_ROOT / "contracts" / "v1" / "fixtures" / "apparel-handoff.valid.json").read_bytes(),
        )
        request = {
            "schema_version": "apparel-compile-request/v1",
            "folder_id": "handoff-sku",
            "source_folder": str(self.source),
            "sources": [path.name for path in sorted(self.source.iterdir())],
            "vision_role_map": [
                {"file": "front-a.png", "role": "color_front", "color_identity": " NAVY "},
                {"file": "front-b.png", "role": "color_front", "color_identity": "ivory"},
                {"file": "back-a.png", "role": "main_back", "color_identity": "navy"},
            ],
            "requested_outputs": [
                {"id": "navy", "filename": "navy.png", "view": "front", "color_identity": "navy", "product_description": "knit top", "visible_details": []},
                {"id": "ivory", "filename": "ivory.png", "view": "front", "color_identity": "ivory", "product_description": "knit top", "visible_details": []},
            ],
        }
        handoff = mpw_compiler.compile_request(request)
        path = self.root / "handoff.json"
        path.write_text(json.dumps(handoff), encoding="utf-8")
        coordinator = fullset.prepare_folder(path, self.run_root)
        self.assertEqual(coordinator["task_count"], 2)
        self.assertEqual(coordinator["candidate_sets"], ["candidate-set-1", "candidate-set-2"])
        self.assertEqual(coordinator["output_inventory"], ["navy.png", "ivory.png"])


if __name__ == "__main__":
    unittest.main()
