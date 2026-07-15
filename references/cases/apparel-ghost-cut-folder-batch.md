# Apparel Ghost-Cut Folder Batch

## Activation

Use for a product folder that must become a coherent pure-white ghost-cut or clean-product-cut family. Source folders stay read-only; outputs go to a separate dated session root.

## Public folder intake

An explicit Vision role map is preferred when visual color names are known. Ordinary folders may omit it and use:

- `f1`: primary front;
- `b1`: primary back;
- `cN`: alternate/color fronts;
- `dN`: detail/material evidence;
- `sN`: composite-only sources.

Filename roles never claim a visual color name. Auto-mapped `cN` values are opaque identities. The complete source inventory is always attached together.

## Attempts are not colors

`candidate_attempt_count` is independent from product color count and defaults to three. Each `candidate-set-N` generates the complete requested output inventory from originals. A one-color product still receives three attempts; multiple colors do not silently multiply or reduce attempts.

## Generation contract

Every task receives the same immutable originals, role map, MPW folder master, QC contract, and output inventory. It owns a disjoint browser session, candidate root, downloads, ledger, and provenance. It must not overwrite, recover from another session, chain a generated image, or change provider/model silently.

Silhouette correction and white-background extension happen in one generation. Uniform `#FFFFFF`, no floor/shadow/halo/gradient, source-supported construction, and consistent canvas/occupancy/lighting remain hard locks.

## Scheduling and selection

Read the live delegation ceiling and pass it as `--runtime-limit`. Pack whole folders without splitting or reducing attempts. Generation keeps the sequential pilot, independent QC, bounded fan-out, and failed-item retry path.

Vision scores every candidate cut and every cross-attempt pair. The default selector is mixed: each output cut independently takes the highest-fidelity candidate that passes support removal, pure white/no shadow, and no invented detail, with ties resolving to the lowest attempt index. Every pairwise similarity among the chosen cuts must be scored and clear the 80% gate or selection fails closed. An explicit `selection_mode: whole-set` keeps one coherent candidate set; unknown modes fail closed. Provenance records the selection mode, per-cut source set, hashes, fidelity, and rejected alternatives. `selected/` is written by staging plus atomic rename and contains only final files plus provenance.

## Recovery

- Partial attempts remain evidence, not deliverables.
- Missing or modified ledger-owned outputs fail closed.
- A shared systematic failure starts a fresh attempt from originals after the prompt delta is revised.
- Resume requires matching hashes, sizes, contract identity, and provenance.
