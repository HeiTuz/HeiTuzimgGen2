#!/usr/bin/env python3
"""Portable, dependency-free validator for the shared prompt contracts."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

CONTRACT_ROOT = Path(__file__).resolve().parent
SCHEMA_FILES = {
    "garden-recipe/v1": CONTRACT_ROOT / "v1" / "garden-recipe.schema.json",
    "prompt-bundle/v1": CONTRACT_ROOT / "v1" / "prompt-bundle.schema.json",
    "source-evidence-index/v1": CONTRACT_ROOT / "v1" / "source-evidence-index.schema.json",
    "production-adapter-options/v1": CONTRACT_ROOT / "v1" / "production-adapter-options.schema.json",
    "imggen2-production-record/v1": CONTRACT_ROOT / "v1" / "imggen2-production-record.schema.json",
    "mpw-recompile-request/v1": CONTRACT_ROOT / "v1" / "mpw-recompile-request.schema.json",
}
FORBIDDEN_KEYS = {
    "api_key",
    "authorization",
    "chat_id",
    "file_path",
    "image_path",
    "original",
    "original_path",
    "password",
    "raw_caption",
    "raw_source",
    "secret",
    "source_path",
    "user_id",
}
PATH_VALUE_RE = re.compile(
    r"(?:^|\s)(?:~/(?:[^\s]+)|/(?:Users|home|tmp|var|private|Volumes)/[^\s]+|[A-Za-z]:\\[^\s]+|file://[^\s]+|data:image/[^\s]+)",
    re.IGNORECASE,
)
FILE_DEPENDENCY_RE = re.compile(
    r"\b(?:read|load|open|see|consult)\s+(?:the\s+)?(?:file|path)\b|(?:파일|경로)(?:을|를|에서|의)?\s*(?:읽|열|참조)",
    re.IGNORECASE,
)


def canonical_hash(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _type_matches(value: Any, expected: str) -> bool:
    if expected == "null":
        return value is None
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "string":
        return isinstance(value, str)
    if expected == "array":
        return isinstance(value, list)
    if expected == "object":
        return isinstance(value, dict)
    return False


def _resolve_ref(root_schema: dict[str, Any], ref: str) -> dict[str, Any]:
    if not ref.startswith("#/"):
        raise ValueError(f"external_ref_not_supported:{ref}")
    node: Any = root_schema
    for part in ref[2:].split("/"):
        node = node[part.replace("~1", "/").replace("~0", "~")]
    if not isinstance(node, dict):
        raise ValueError(f"invalid_ref_target:{ref}")
    return node


def _schema_errors(value: Any, schema: dict[str, Any], root_schema: dict[str, Any], path: str) -> list[str]:
    if "$ref" in schema:
        return _schema_errors(value, _resolve_ref(root_schema, schema["$ref"]), root_schema, path)

    errors: list[str] = []
    if "const" in schema and value != schema["const"]:
        errors.append(f"{path}: expected_const:{schema['const']!r}")
        return errors
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: expected_one_of:{schema['enum']!r}")
        return errors

    expected = schema.get("type")
    if expected is not None:
        choices = expected if isinstance(expected, list) else [expected]
        if not any(_type_matches(value, choice) for choice in choices):
            errors.append(f"{path}: expected_type:{'|'.join(choices)}")
            return errors
    if "oneOf" in schema:
        matches = sum(
            not _schema_errors(value, branch, root_schema, path)
            for branch in schema["oneOf"]
        )
        if matches != 1:
            errors.append(f"{path}: one_of_match_count:{matches}")

    if isinstance(value, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in value:
                errors.append(f"{path}.{key}: required")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for key in value:
                if key not in properties:
                    errors.append(f"{path}.{key}: additional_property")
        for key, child in properties.items():
            if key in value:
                errors.extend(_schema_errors(value[key], child, root_schema, f"{path}.{key}"))

    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            errors.append(f"{path}: min_items:{schema['minItems']}")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            errors.append(f"{path}: max_items:{schema['maxItems']}")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                errors.extend(_schema_errors(item, item_schema, root_schema, f"{path}[{index}]"))

    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            errors.append(f"{path}: min_length:{schema['minLength']}")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            errors.append(f"{path}: max_length:{schema['maxLength']}")
        pattern = schema.get("pattern")
        if pattern and not re.search(pattern, value):
            errors.append(f"{path}: pattern_mismatch:{pattern}")

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path}: minimum:{schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{path}: maximum:{schema['maximum']}")

    return errors


def _privacy_errors(value: Any, path: str = "$") -> list[str]:
    errors: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = key.casefold().replace("-", "_")
            if normalized in FORBIDDEN_KEYS:
                errors.append(f"{path}.{key}: forbidden_private_key")
            errors.extend(_privacy_errors(child, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            errors.extend(_privacy_errors(child, f"{path}[{index}]"))
    elif isinstance(value, str) and PATH_VALUE_RE.search(value):
        errors.append(f"{path}: forbidden_path_or_embedded_original")
    return errors


def _garden_semantic_errors(value: dict[str, Any]) -> list[str]:
    errors = _privacy_errors(value)
    observations = value.get("observations", {})
    observed_ids: set[str] = set()
    if isinstance(observations, dict):
        for axis, evidence in observations.items():
            if not isinstance(evidence, dict):
                continue
            status = evidence.get("status")
            items = evidence.get("items")
            if status == "observed" and isinstance(items, list) and not items:
                errors.append(f"$.observations.{axis}.items: observed_requires_item")
            if status in {"not_observable", "not_applicable"} and items:
                errors.append(f"$.observations.{axis}.items: unavailable_axis_must_be_empty")
            if isinstance(items, list):
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    observation_id = item.get("observation_id")
                    if isinstance(observation_id, str):
                        if observation_id in observed_ids:
                            errors.append(f"$.observations.{axis}: duplicate_observation_id:{observation_id}")
                        observed_ids.add(observation_id)
    inference_ids: set[str] = set()
    for index, inference in enumerate(value.get("inferences", [])):
        if not isinstance(inference, dict):
            continue
        inference_id = inference.get("inference_id")
        if isinstance(inference_id, str):
            if inference_id in inference_ids:
                errors.append(f"$.inferences[{index}].inference_id: duplicate")
            inference_ids.add(inference_id)
        for observation_id in inference.get("based_on", []):
            if observation_id not in observed_ids:
                errors.append(f"$.inferences[{index}].based_on: unknown_observation_id:{observation_id}")
    return errors


def _bundle_semantic_errors(value: dict[str, Any], recipe: dict[str, Any] | None) -> list[str]:
    errors = _privacy_errors(value)
    handoff = value.get("handoff", {})
    if isinstance(handoff, dict):
        block_ids: set[str] = set()
        for index, block in enumerate(handoff.get("prompt_blocks", [])):
            if not isinstance(block, dict):
                continue
            block_id = block.get("block_id")
            if isinstance(block_id, str):
                if block_id in block_ids:
                    errors.append(f"$.handoff.prompt_blocks[{index}].block_id: duplicate")
                block_ids.add(block_id)
            text = block.get("text")
            count = block.get("unicode_char_count")
            if isinstance(text, str):
                actual = len(text)
                if count != actual:
                    errors.append(f"$.handoff.prompt_blocks[{index}].unicode_char_count: expected:{actual}")
                if actual > 2000:
                    errors.append(f"$.handoff.prompt_blocks[{index}].text: unicode_limit:2000")
                if FILE_DEPENDENCY_RE.search(text):
                    errors.append(f"$.handoff.prompt_blocks[{index}].text: external_file_dependency")

    if recipe is not None:
        if value.get("source_recipe", {}).get("recipe_id") != recipe.get("recipe_id"):
            errors.append("$.source_recipe.recipe_id: recipe_id_mismatch")
        expected_hash = canonical_hash(recipe)
        if value.get("source_recipe", {}).get("recipe_hash") != expected_hash:
            errors.append(f"$.source_recipe.recipe_hash: expected:{expected_hash}")
        if handoff.get("immutable_locks") != recipe.get("locks"):
            errors.append("$.handoff.immutable_locks: recipe_lock_drift")
        intended_use = recipe.get("intended_use", {})
        if handoff.get("mode") != intended_use.get("mode"):
            errors.append("$.handoff.mode: recipe_mode_drift")
        if handoff.get("engine") != intended_use.get("engine"):
            errors.append("$.handoff.engine: recipe_engine_drift")
    return errors


AXIS_DELTA = {
    "goal_fit": "clarify_goal_fit",
    "text_accuracy": "resolve_text_from_source",
    "material_realism": "clarify_material_realism",
    "layout": "clarify_layout",
}
PROMO_CHECKS = [
    "physical_type_subject_interaction",
    "generic_card_regression",
    "printed_meta_ui_not_literal",
    "color_lock_2_to_3",
    "finishing_devices_1_to_3",
    "korean_glyph_mask_safety",
]
GEOMETRY = {
    "1:1": "1024x1024",
    "3:4": "1024x1536",
    "4:3": "1536x1024",
    "9:16": "1024x1536",
    "16:9": "1536x1024",
}


def _unique_sorted_strings(values: Any, path: str) -> list[str]:
    if not isinstance(values, list) or not all(isinstance(item, str) for item in values):
        return []
    errors: list[str] = []
    if len(values) != len(set(values)):
        errors.append(f"{path}: duplicate")
    if values != sorted(values):
        errors.append(f"{path}: not_sorted")
    return errors


def _source_index_semantic_errors(value: dict[str, Any]) -> list[str]:
    references = value.get("references", [])
    errors = _unique_sorted_strings(
        [item.get("reference_id") for item in references if isinstance(item, dict)],
        "$.references.reference_id",
    )
    return errors + _privacy_errors(value)


def _options_semantic_errors(value: dict[str, Any]) -> list[str]:
    errors = _privacy_errors(value)
    output_path = value.get("output_path")
    if isinstance(output_path, str):
        parts = output_path.replace("\\", "/").split("/")
        if output_path.startswith(("/", "~")) or ".." in parts or "." in parts or "\\" in output_path:
            errors.append("$.output_path: unsafe_relative_path")
    expected_size = GEOMETRY.get(value.get("ar"))
    if expected_size is not None and value.get("size") != expected_size:
        errors.append("$.size: production_geometry_mismatch")
    applicability = value.get("qc_applicability", {})
    evidence_ids = applicability.get("evidence_reference_ids", []) if isinstance(applicability, dict) else []
    errors.extend(_unique_sorted_strings(evidence_ids, "$.qc_applicability.evidence_reference_ids"))
    if isinstance(applicability, dict) and (
        applicability.get("promotional") or applicability.get("rendered_text_expected")
    ) and not evidence_ids:
        errors.append("$.qc_applicability.evidence_reference_ids: required_when_applicable")
    return errors


def _production_semantic_errors(value: dict[str, Any]) -> list[str]:
    errors = _privacy_errors(value)
    errors.extend(_unique_sorted_strings(value.get("reference_ids", []), "$.reference_ids"))
    expected_size = GEOMETRY.get(value.get("ar"))
    if expected_size is not None and value.get("size") != expected_size:
        errors.append("$.size: production_geometry_mismatch")
    return errors


def _recompile_semantic_errors(value: dict[str, Any]) -> list[str]:
    errors = _privacy_errors(value)
    axes = value.get("failed_axes", [])
    checks = value.get("failed_promo_checks", [])
    if isinstance(axes, list) and isinstance(checks, list) and not axes and not checks:
        errors.append("$: recompile_failure_fact_required")
    for path, items in (("$.failed_axes", axes), ("$.failed_promo_checks", checks)):
        if isinstance(items, list) and len(items) != len(set(item for item in items if isinstance(item, str))):
            errors.append(f"{path}: duplicate")
    expected_reasons = [
        *(f"qc_axis:{axis}" for axis in axes if axis in AXIS_DELTA),
        *(f"promo_check:{check}" for check in checks if check in PROMO_CHECKS),
    ]
    expected_deltas = [
        *(AXIS_DELTA[axis] for axis in axes if axis in AXIS_DELTA),
        *(f"resolve_promo_{check}" for check in checks if check in PROMO_CHECKS),
    ]
    if value.get("reason_codes") != expected_reasons:
        errors.append("$.reason_codes: recompile_reason_mapping_mismatch")
    if value.get("requested_delta_codes") != expected_deltas:
        errors.append("$.requested_delta_codes: recompile_delta_mapping_mismatch")
    return errors
def load_schema(schema_version: str) -> dict[str, Any]:
    path = SCHEMA_FILES.get(schema_version)
    if path is None:
        raise ValueError(f"unsupported_schema_version:{schema_version}")
    return json.loads(path.read_text(encoding="utf-8"))


def validate_document(value: Any, recipe: dict[str, Any] | None = None) -> list[str]:
    if not isinstance(value, dict):
        return ["$: expected_type:object"]
    schema_version = value.get("schema_version")
    if not isinstance(schema_version, str):
        return ["$.schema_version: required"]
    try:
        schema = load_schema(schema_version)
    except ValueError as exc:
        return [f"$.schema_version: {exc}"]
    errors = _schema_errors(value, schema, schema, "$")
    if schema_version == "garden-recipe/v1":
        errors.extend(_garden_semantic_errors(value))
    elif schema_version == "prompt-bundle/v1":
        errors.extend(_bundle_semantic_errors(value, recipe))
    elif schema_version == "source-evidence-index/v1":
        errors.extend(_source_index_semantic_errors(value))
    elif schema_version == "production-adapter-options/v1":
        errors.extend(_options_semantic_errors(value))
    elif schema_version == "imggen2-production-record/v1":
        errors.extend(_production_semantic_errors(value))
    elif schema_version == "mpw-recompile-request/v1":
        errors.extend(_recompile_semantic_errors(value))
    return sorted(set(errors))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate GardenRecipe and PromptBundle JSON")
    parser.add_argument("document", type=Path)
    parser.add_argument("--recipe", type=Path, help="GardenRecipe used to prove PromptBundle provenance and lock preservation")
    parser.add_argument("--json", action="store_true", help="Emit a machine-readable validation result")
    args = parser.parse_args(argv)

    try:
        value = load_json(args.document)
        recipe = load_json(args.recipe) if args.recipe else None
    except (OSError, json.JSONDecodeError) as exc:
        result = {"ok": False, "errors": [f"input_error:{exc}"]}
    else:
        errors = validate_document(value, recipe)
        result = {"ok": not errors, "schema_version": value.get("schema_version") if isinstance(value, dict) else None, "errors": errors}

    if args.json:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    elif result["ok"]:
        print(f"OK {result['schema_version']} {args.document}")
    else:
        for error in result["errors"]:
            print(f"FAIL {error}", file=sys.stderr)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
