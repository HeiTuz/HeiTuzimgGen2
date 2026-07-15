# DINT shared-folder apparel batch

## 1. Minimal Discord request

```text
@DINT 제품사진 일괄보정해줘.
공유폴더: \\Dint\00.딘트공유\상품촬영\2026SS\상품코드
```

## 2. Input tree

```text
상품코드/
├── f1.jpg
├── b1.jpg
└── d1_원단.jpg
```

## 3. Filename-to-role mapping

| Filename token | Role | Shot role | Notes |
| --- | --- | --- | --- |
| `f1` | `color_front` | `front` | `color_identity` is `default`. |
| `b1` | `main_back` | `back` | Main back cut. |
| `fN` (`N >= 2`) | `front_variant` | `front-variant` | Front variant. |
| `bN` (`N >= 2`) | `back_variant` | `back-variant` | Back variant. |
| `cN` | `color_front` | `color-front` | `color_identity` is the opaque token such as `c2`. |
| `dN` | `fabric_detail` | `fabric-detail` | An optional suffix is a descriptor; `d1_원단.jpg` has descriptor `원단`. |
| `sN` | `composite_source` | `composite-source` | Composite source. |

A token may have an optional `_descriptor` suffix. Roles identify the shot, never a visual color name: color identities remain opaque (`default`, `c2`, and so on). Unknown tokens and duplicate token slots fail closed; rename or remove the conflicting source before retrying. A batch also fails closed without `f1` or a `cN` front cut.

## 4. Helper invocation and Vision handoff

Run the helper with the shared folder path only:

```bash
python scripts/folder_batch_prepare.py --input-dir "//Dint/00.딘트공유/상품촬영/2026SS/상품코드" --mode apparel-product-correction --publish-subfolder auto
```

The command creates private manifests under its work root and prints `prepare-summary.json` content to standard output. Its `vision-handoff.json` contains a role map and source verification data such as:

```json
{
  "schema_version": 1,
  "folder_id": "상품코드",
  "source_folder": "//Dint/00.딘트공유/상품촬영/2026SS/상품코드",
  "sources": [
    {
      "name": "b1.jpg",
      "sha256": "<sha256>",
      "size": 123456,
      "role": "main_back",
      "shot_role": "back"
    },
    {
      "name": "d1_원단.jpg",
      "sha256": "<sha256>",
      "size": 123456,
      "role": "fabric_detail",
      "shot_role": "fabric-detail",
      "descriptor": "원단"
    },
    {
      "name": "f1.jpg",
      "sha256": "<sha256>",
      "size": 123456,
      "role": "color_front",
      "shot_role": "front",
      "color_identity": "default"
    }
  ],
  "verification_tasks": [
    "verify filename role mapping",
    "verify construction evidence",
    "verify occlusions",
    "verify product grouping"
  ],
  "correction_contract": "<default apparel correction contract>",
  "qc_contract": "<default apparel QC contract>"
}
```

## 5. Default correction and QC contract

For `apparel-product-correction`, preserve the product's original design, color, material cues, trims, graphics, and details. Apply only mild, natural fit cleanup where folds or collapse came from the shoot setup. Remove mannequins, hangers, racks, stands, hands, people, text, and watermarks when they are not part of the product. Never redesign the garment or invent unsupported construction.

Independent Vision QC rejects retained supports, excessive fit changes, altered design, color, material, trim, graphic, or detail, and invented garment construction. It also verifies role mapping, construction evidence, occlusions, and product grouping against the complete source inventory.

## 6. Private work root and published result

The helper keeps preparation artifacts outside the source folder:

```text
<private-work-root>/
├── folder-contract.json
├── vision-handoff.json
├── output-plan.json
├── prepare-summary.json
└── runs/
```

After Vision selection, publish with the selected root using the same input folder and a non-existing result name:

```bash
python scripts/folder_batch_prepare.py --input-dir "//Dint/00.딘트공유/상품촬영/2026SS/상품코드" --publish-from "<private-work-root>/runs/상품코드/selected" --publish-subfolder auto
```
 The published source-folder subdirectory contains final PNGs and `batch-summary.json` only:

```text
상품코드/
└── AI_RESULT_YYYYMMDD_HHMMSS/
    ├── f1.png
    ├── b1.png
    ├── d1_원단.png
    └── batch-summary.json
```

`folder-contract.json`, `vision-handoff.json`, `output-plan.json`, `prepare-summary.json`, and `runs/` are private artifacts and never enter the source folder.

## 7. Completion JSON and Discord completion message

A successful publication writes `batch-summary.json` with this shape:

```json
{
  "schema_version": 1,
  "source_folder": "//Dint/00.딘트공유/상품촬영/2026SS/상품코드",
  "result_folder": "//Dint/00.딘트공유/상품촬영/2026SS/상품코드/AI_RESULT_20260715_143000",
  "published": [
    {
      "filename": "b1.png",
      "sha256": "<sha256>",
      "size": 123456,
      "output_id": "b1",
      "source_candidate_set": "candidate-set-1"
    },
    {
      "filename": "d1_원단.png",
      "sha256": "<sha256>",
      "size": 123456,
      "output_id": "d1_원단",
      "source_candidate_set": "candidate-set-2"
    },
    {
      "filename": "f1.png",
      "sha256": "<sha256>",
      "size": 123456,
      "output_id": "f1",
      "source_candidate_set": "candidate-set-1"
    }
  ],
  "counts": {
    "published": 3,
    "skipped": 0,
    "failed": 0
  },
  "qc_status": {
    "selection_mode": "mixed",
    "min_family_similarity_gate": 0.8,
    "score": {
      "fidelity_sum": 2.85,
      "min_similarity": 0.93,
      "average_similarity": 0.96
    }
  },
  "provenance_sha256": "<sha256>",
  "completed_at": "20260715_143000"
}
```

```text
DINT 일괄보정이 완료되었습니다. 결과는 \\Dint\00.딘트공유\상품촬영\2026SS\상품코드\AI_RESULT_20260715_143000 에 저장되었습니다.
```

## 8. Delivery semantics

Direct Discord image attachments return final files to the requesting channel or thread as attachments. A shared-folder path request saves final files to the new `AI_RESULT_<timestamp>` subfolder inside the requested product folder, and the completion message reports that path back to the requesting channel or thread. `batch-summary.json` is the machine-readable source for that report.

## 9. Resume, retry, and source-read-only guarantees

The source originals are read-only: they remain byte-identical after success, failure, interruption, and retry. Publication verifies selected-file hashes before copying and after staging. It never overwrites a result folder; a collision requires a fresh `--timestamp`, producing a new `AI_RESULT_<timestamp>` name. Interrupted or failed publication cleans up its staging directory and can be retried after fixing the selected root.

## 10. Windows notes

- `--input-dir` accepts a Windows drive-letter path or UNC path on Windows. Preserve Unicode and spaces by quoting the whole argument.
- For Windows long paths, use the `\\?\` prefix where required by the environment.
- SMB copy or rename failures leave originals untouched; the publication stage is cleaned up, the error includes the operating-system failure, and publication can be retried.
- Junctions, symlinks, and other reparse points are rejected in the source folder rather than followed.
- `Thumbs.db`, `desktop.ini`, and other ordinary artifacts are ignored. Hidden image files still fail closed because they would desynchronize the complete image inventory.
- Existing `AI_RESULT_*` directories are excluded from future source inventory.

```text
상품코드/
├── f1.jpg
├── b1.jpg
├── d1_원단.jpg
└── AI_RESULT_20260715_143000/
    ├── f1.png
    ├── b1.png
    ├── d1_원단.png
    └── batch-summary.json
```
