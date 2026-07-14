import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import consume_image_handoff as handoff


class ImageHandoffTests(unittest.TestCase):
    def valid(self):
        return {
            "schema_version": "heituz-image-production-handoff/v1",
            "job_id": "catalog-cup-01",
            "operation": "edit",
            "prompt": "A blue ceramic cup on natural linen",
            "negative_prompt": "No text or logos",
            "aspect_ratio": "1:1",
            "image_size": "1024x1024",
            "input_images": [{"path": "inputs/cup.png", "role": "subject"}],
            "output": {"filename": "cup-final.png"},
            "metadata": {"compiler": "portable-test"},
        }

    def test_accepts_portable_contract(self):
        value = handoff.validate_handoff(self.valid())
        self.assertEqual(value["output"]["filename"], "cup-final.png")

    def test_edit_requires_at_least_one_input_image(self):
        value = self.valid()
        value.pop("input_images")
        with self.assertRaisesRegex(handoff.HandoffError, "edit handoffs require"):
            handoff.validate_handoff(value)
        value["operation"] = "generate"
        self.assertEqual(handoff.validate_handoff(value)["input_images"], [])

    def test_rejects_uppercase_output_from_mpw_request(self):
        value = self.valid()
        value["output"]["filename"] = "CUP-FINAL.PNG"
        with self.assertRaisesRegex(handoff.HandoffError, "output.filename"):
            handoff.validate_handoff(value)

    def test_rejects_absolute_and_parent_paths(self):
        for filename in ("/tmp/output.png", "../output.png", "C:\\output.png"):
            value = self.valid()
            value["output"]["filename"] = filename
            with self.subTest(filename=filename), self.assertRaises(handoff.HandoffError):
                handoff.validate_handoff(value)

    def test_rejects_nonportable_input_references(self):
        for reference in ("../input.png", r"folder\input.png", "~/input.png", "https://user@example.invalid/input.png"):
            value = self.valid()
            value["input_images"][0]["path"] = reference
            with self.subTest(reference=reference), self.assertRaises(handoff.HandoffError):
                handoff.validate_handoff(value)

    def test_rejects_unknown_or_host_routing_fields(self):
        value = self.valid()
        value["worker_id"] = "private-host-route"
        with self.assertRaisesRegex(handoff.HandoffError, "unsupported fields"):
            handoff.validate_handoff(value)

    def test_schema_accepts_twenty_but_executor_supports_four_images(self):
        value = self.valid()
        value["input_images"] = [
            {"path": f"input-{index}.png", "role": "reference"} for index in range(5)
        ]
        self.assertEqual(len(handoff.validate_handoff(value)["input_images"]), 5)
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp, "handoff.json")
            source.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaisesRegex(handoff.HandoffError, "at most four"):
                handoff.consume_handoff(source, Path(temp))

    def test_https_reference_validates_but_requires_materialization(self):
        value = self.valid()
        value["input_images"] = [{"path": "https://example.invalid/input.png", "role": "subject"}]
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp, "handoff.json")
            source.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaisesRegex(handoff.HandoffError, "materialized"):
                handoff.consume_handoff(source, Path(temp))

    def test_adapter_resolves_paths_and_preserves_transport_boundary(self):
        value = self.valid()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "handoff.json"
            source.write_text(json.dumps(value), encoding="utf-8")
            expected_image = (root / "inputs/cup.png").resolve()
            expected_output = (root / "results/cup-final.png").resolve()
            with patch.object(handoff.transport, "run", return_value={"live": False}) as run:
                result = handoff.consume_handoff(source, root / "results")
            effective_prompt = (
                value["prompt"]
                + "\n\nNegative requirements: No text or logos"
                + "\nRequested aspect ratio: 1:1"
                + "\nRequested image size: 1024x1024"
            )
            run.assert_called_once_with(effective_prompt, expected_output, [expected_image], False)
            self.assertEqual(result["job_id"], value["job_id"])
            self.assertEqual(result["transport"], {"live": False})

    def test_installed_schema_matches_shared_contract_shape(self):
        schema = json.loads(
            Path(__file__).resolve().parents[1]
            .joinpath("contracts/v1/image-production-handoff.schema.json")
            .read_text(encoding="utf-8")
        )
        self.assertEqual(
            schema["required"],
            ["schema_version", "job_id", "operation", "prompt", "output"],
        )
        self.assertEqual(schema["properties"]["input_images"]["maxItems"], 20)
        edit_rule = schema["allOf"][0]
        self.assertEqual(edit_rule["if"]["properties"]["operation"]["const"], "edit")
        self.assertEqual(edit_rule["then"]["properties"]["input_images"]["minItems"], 1)
        self.assertEqual(
            schema["properties"]["output"]["properties"]["filename"]["pattern"],
            r"^[^/\\]+\.(png|jpg|jpeg|webp)$",
        )


if __name__ == "__main__":
    unittest.main()
