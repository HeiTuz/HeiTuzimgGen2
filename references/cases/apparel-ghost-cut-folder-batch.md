# Apparel Ghost-Cut Folder Batch

## Activation

Use for a product folder that must become a coherent pure-white ghost-cut or clean-product-cut family. The source folder stays read-only; output goes to a dated session root.

## Roles and task count

Vision owns pixel observations, role labels, source-evidence coverage, occlusion notes, and explicit `color_identity`. HeiTuzMPW owns folder master and final per-output prompts. HeiTuzimgGen2 owns browser-session isolation, dynamic candidate tasks, selection, ledgers, and delivery provenance.

Count task sets only from role-map records whose `role` is exactly `color_front`:

1. require explicit non-empty `color_identity`;
2. normalize with Unicode NFKC, collapsed whitespace, and case folding;
3. count unique normalized values;
4. do not infer color from filenames;
5. do not count main-back or fabric/detail records, including duplicate evidence for the same color.

`0` colors is `blocked`; `1` creates `task-1` / `candidate-set-1`; `4` creates `task-1..4` / `candidate-set-1..4`. There is no default task count.

## Full-folder candidate contract

Every task receives the same immutable complete source inventory, Vision role map, MPW folder master, QC contract, and full output inventory. Each task independently generates every requested cut inside its own candidate root with its own browser page/session, downloads, ledger, and provenance. It must not overwrite, recover from another session, use a generated image as an input, or change provider/model silently.

The main-color front plus back and fabric/detail define construction and material evidence. Every color front defines its own colorway, visible graphic, neckline, sleeve length, hem, and silhouette. A hidden region without coverage is `insufficient_source_evidence`; do not invent construction.

## Prompt and QC locks

Every output prompt is self-contained and at most 2,000 characters. It fixes exact view/color, source-supported construction/material/trim/print, complete support removal, uniform `#FFFFFF`, no shadow/halo/floor/gradient, source-only reconstruction, and series canvas/occupancy/centerline/scale/lighting consistency.

Vision accepts candidates only when source fidelity is scored, support removal is true, white/no-shadow is true, and invented detail is false. The final family must clear a minimum pairwise similarity of `0.80` across silhouette, scale, placement, material, lighting, and style.

## Scheduling and selection

Read the live delegation ceiling. Pack whole folders into generator waves without splitting one folder's N tasks. If N exceeds the ceiling, mark that folder `blocked`; do not reduce N. Selectors wait for the generator specs of their own folder.

The selector enumerates all valid dynamic-N cross-set combinations. It rejects combinations lacking required pairwise evidence or falling below the 0.80 gate. It maximizes source fidelity first, then minimum and average family similarity. `selected/` is written by staging plus atomic rename. Provenance includes every selected source task/set/path/hash and one rejected-alternative row for every other candidate set, including unavailable candidates.

## Recovery

- Partial sets remain partial evidence.
- Missing candidates are acceptable only when every output still has a valid candidate and every selected pair has an assessment.
- No passing combination writes nothing to `selected/`.
- A shared systematic failure requires a new dynamic-N full-folder run from originals after revising the folder master.
- Resume only accepts matching ledger-owned output hashes/sizes and a complete selected tree with matching provenance.
- Do not open browser generation during network-free validation.

## Progress wording

Report the furthest real stage: `source inventory`, `Vision role map`, `folder master`, `N-task dry-run`, `candidate-set-N`, `Vision cross-selection`, or `selected delivery`. Do not call prompt compilation or scheduling image generation.
