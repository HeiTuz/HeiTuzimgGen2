# Browser GPT Dynamic Full-Set Selector

## Trigger and ownership

Use this branch when an apparel product folder needs independent complete-folder candidate sets followed by Vision cross-selection. The candidate-set count is **not fixed**: it equals the number of unique normalized `color_identity` values on Vision role-map records whose `role` is exactly `color_front`.

- `color_identity` normalization: Unicode NFKC, collapsed whitespace, case folding.
- Color front records must state an explicit non-empty identity; filenames are identifiers, never color evidence.
- Back and detail records never increase the count. Repeated front/back/detail evidence for one normalized color still makes one task.
- Zero unique front identities is `blocked`. One identity creates one task. Four identities create four tasks.

The coordinator/selector is `../scripts/apparel_three_fullset.py`; one browser task executor is `../scripts/browser_gpt_apparel_task.py`; the input contract is `apparel-three-fullset-folder.schema.json`. The portable compiler handoff schema is `apparel-handoff.schema.json`.

## Prepare and schedule

`prepare` hashes one immutable folder contract and creates `task-N` → `candidate-set-N/` for every normalized front-color identity. Every task receives the same complete original source inventory, Vision role map, MPW folder master, QC contract, and complete output inventory. Only its candidate root, browser page/session, downloads, ledger, and provenance ownership differ.

```bash
python scripts/apparel_three_fullset.py prepare \
  --contract /path/to/folder-contract.json \
  --run-root /path/to/non-source-output-root \
  --runtime-limit 20
```

Read the live delegation cap before scheduling and pass the observed value to `--runtime-limit`. A generator wave packs whole folders only: a folder with N tasks is never split. If any folder's N exceeds the cap, preparation is `blocked`; it never falls back to fewer candidate sets. At cap 20, four-task folders pack five per generator wave. Selectors run only after their folder's generator task specs finish.

## Browser-task contract

Dry-run is the default:

```bash
python scripts/browser_gpt_apparel_task.py \
  --task-spec /path/to/task-1.json
```

The live task attaches every original and the immutable contract once, opens one dedicated browser session, and generates every requested output using only the original inventory. It accepts only a fresh image observed after the corresponding request in that same page, writes exclusively, and records hash/size/session provenance in its own ledger.

No overwrite, cross-session recovery, generated-result chaining, or provider/model fallback is allowed. Resume accepts only a ledger-owned output whose hash and size still match.

## Vision selector and provenance

Vision evaluates every available candidate with source fidelity, support removal, pure-white/no-shadow, no-invented-detail, and pairwise family similarity. The report binds to the immutable shared-contract hash. The selector enumerates all valid dynamic-N combinations, rejects incomplete pairwise evidence and combinations whose minimum similarity is below `0.80`, then maximizes source fidelity, minimum similarity, and average similarity in that order.

`selected/` is staged and atomically renamed. `selected/provenance.json` records each selected task/set/path/hash plus a rejected-alternative row for every other dynamic candidate set, including unavailable candidates. Missing candidates are allowed only when every output still has at least one valid candidate and all chosen cross-output comparisons are present.

## Network-free verification

```bash
python -m unittest discover \
  -s scripts \
  -p 'test_*.py' -v
python -m py_compile scripts/*.py
```

Tests cover 0/1/4 front-color identities, duplicate identities, no filename inference, identical inventories with disjoint roots, cap-20 packing, over-cap blocking, dynamic selection, the 80% gate, missing candidates, resume/no-overwrite/provenance, and the portable producer-to-consumer handoff. They do not open a browser or generate live images.
