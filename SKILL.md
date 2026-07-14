---
name: HeiTuzimgGen2
description: "Generate and edit images through the official Codex CLI using ChatGPT subscription authentication. Includes provenance-safe single-image transport, resumable JSONL batches, independent QC, and an optional dynamic apparel full-set workflow."
version: 1.6.0
author: HeiTuz
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [image-generation, image-editing, chatgpt]
    category: creative
---

# HeiTuzimgGen2

Generate or edit images through the official Codex CLI with an authenticated ChatGPT subscription. The skill remains a standalone transport and result-QC tool. When `HeiTuzMPW` is installed, it may own final IMAGE prompt compilation and emit the shared portable handoff described below.

## Capabilities

- text-to-image, edits, and two-to-four reference compositions;
- dry-run-first transport with exclusive output creation and session-scoped artifact provenance;
- resumable JSONL batches with a sequential pilot, bounded fan-out, ledger ownership, selective retry, and independent QC reconciliation;
- optional apparel full-set preparation: one complete candidate set per unique normalized Vision `color_front` identity, followed by cross-set selection at a minimum 80% family-similarity gate.

Never use api-key billing, private endpoints, DOM automation, cookie extraction, silent provider fallback, or a model claim not supported by returned evidence. Never fall back to a different provider, API route, browser session, or model. never turn a requested label into an attestation: `observed_model` and `model_identity_attested` stay unset unless supported evidence exists. For delivery, use `send_message` with a document/file attachment; printing the path is not delivery evidence.

## Boundaries

- A successful transport proves only that an artifact was obtained; it does not prove visual acceptance or a particular model identity.
- Live image execution requires a fresh approval marker immediately before `--execute`.
- The apparel browser executor is dry-run by default. Live browser execution requires an explicitly configured external adapter through `HEITUZ_BROWSER_ADAPTER_SCRIPT`; it never falls back to another browser, provider, or API.
- Browser candidate tasks receive the same complete source inventory, role map, folder master, QC contract, and output inventory. Their sessions, ledgers, downloads, and candidate roots remain disjoint.

## Core procedures

### Single image or edit

```bash
python scripts/codex_subscription_transport.py \
  --prompt "A blue ceramic cup on natural linen"

python scripts/codex_subscription_transport.py \
  --prompt "Keep the subject; change only the background to warm gray" \
  --image "$PWD/input.png" \
  --output "$PWD/output/edited.png"
```

Both commands are dry-runs until `--execute` is supplied with the required fresh approval marker. See [references/execution-contract.md](references/execution-contract.md).

### Portable compiled handoff

Direct prompt invocation remains fully supported and does not require another skill. An installed `HeiTuzMPW` compiler may instead emit `heituz-image-production-handoff/v1` JSON. Consume it without host-specific routing:

```bash
python scripts/consume_image_handoff.py request.json \
  --output-root "$PWD/generated"
```

This adapter validates [contracts/v1/image-production-handoff.schema.json](contracts/v1/image-production-handoff.schema.json), resolves relative input paths from the handoff file, keeps the output under `--output-root`, and delegates to the same dry-run-first transport. HTTPS input references must first be materialized as relative local files. The handoff must never contain credentials, approval state, session identifiers, or machine/worker routing.

### Folder input batch

When the user supplies an accessible folder path, inventory it with the folder helper before invoking the production batch runner:

```bash
python scripts/folder_batch_prepare.py \
  --input-dir "$PWD/product-sources" \
  --prompt "Final compiled IMAGE edit prompt"
```

With no `--output-root`, the helper creates a marked job under the canonical OS-native `HeiTuzImgGen2` temporary root. Temporary jobs default to 24-hour retention and are removed when `scripts/cleanup_temp_outputs.py` runs; schedule that script for unattended cleanup. The cleaner rejects symlink/reparse roots, verifies Windows ownership before changing any existing root, applies a current-user/SYSTEM-only Windows DACL (or mode `0700` ownership checks on POSIX), preserves unknown or unmarked children, serializes cleanup processes with a root lock, coordinates atomically with process-held job activity locks, treats junction/reparse descendants as leaves, and deletes only expired marked `single-*` or `folder-*` jobs. Quarantine names and cleanup claims are bound to the exact canonical job ID; valid claims abandoned before rename can be recovered after five minutes, while malformed or ambiguous claims are preserved. Stale batch lock files do not block expiry. Temporary jobs are suitable for local work and Discord delivery staging, not permanent storage. When the requester provides an accessible destination outside the managed temporary root, pass `--output-root` and preserve that destination until the requester removes it:

```bash
python scripts/folder_batch_prepare.py \
  --input-dir "$PWD/product-sources" \
  --output-root "$PWD/product-results" \
  --prompt "Final compiled IMAGE edit prompt"
```

When an explicit persistent destination is used, the helper stores the batch manifest under `<output-root>/.heituzimggen2-manifests/` so resume, approval verification, QC, and retry records do not expire separately from the results. With temporary outputs, the manifest remains in the same marked temporary job and expires with it.

The helper recursively inventories up to 500 JPEG, PNG, and WebP inputs (5 GiB total; 512 MiB per reference), rejects every symlink, junction, or reparse-point entry instead of following it, excludes an output subtree only when that subtree is inside the source folder, never mutates originals, and writes one absolute source reference plus one unique relative PNG output per manifest job. It does not copy sources during preparation, so keep them available and unchanged through approval. Immediately before each live transport call, the batch runner copies the approved bytes through an open source handle into a current-user-private managed snapshot, verifies that snapshot against the manifest hash/size evidence, and passes only snapshot paths to Codex; changed bytes fail closed and successful snapshots expire under the normal temporary retention policy. Review the helper's JSON summary, then dry-run the emitted manifest before live approval. A gateway request may use only a path accessible to the Hermes host and authorized for that requester; never claim access to an employee-local path merely because its spelling was supplied.

For Discord delivery, keep temporary outputs until the attachment upload succeeds. Return small result sets as file attachments in the requesting channel or thread; package large batches with the deterministic summary. A printed local path is not delivery evidence. Explicit shared-folder destinations are not auto-cleaned.

### Production batch

Compile a self-contained prompt per cut, prepare a JSONL manifest, then dry-run:

```bash
python scripts/codex_subscription_batch.py \
  --manifest "$PWD/jobs.jsonl" \
  --output-root "$PWD/product-batch" \
  --workers auto
```

The first cut is a sequential capability-and-quality pilot. Bounded fan-out begins only after independent pilot QC passes. The batch owns an atomic ledger; resume is hash-verified against ledger-owned outputs, and failures become a fresh retry manifest. Parallel workers may only own disjoint output roots and ledgers. `--batch-dir` on the single-image helper is still one image call. Read [references/batch-production-contract.md](references/batch-production-contract.md) before batch work.

### Apparel full-set preparation

Vision role records must provide an explicit `color_identity` for every `color_front`. The count is normalized with Unicode NFKC, collapsed whitespace, and case folding:

- zero unique identities: `blocked`;
- one unique identity: one task and `candidate-set-1/`;
- four unique identities: four tasks and `candidate-set-1..4/`.

Do not infer identity from filenames. Back/detail evidence does not add tasks. All N generators receive the complete source inventory and each task generates the full output inventory. The selector admits only hash-verified outputs from a complete task ledger bound to its shared contract, task identity, candidate set, filename, and size; missing or altered outputs block the whole selection. Selection may mix valid candidates across sets only when the entire resulting family clears the 80% gate. Use the observed delegation ceiling as `--runtime-limit`; any over-cap folder is blocked rather than reduced. See [references/browser-gpt-three-fullset-selector.md](references/browser-gpt-three-fullset-selector.md).

## Verification

All verification is network-free:

```bash
python -m unittest discover -s scripts -p 'test_*.py' -v
python -m py_compile scripts/*.py
```

The test suite covers output collision handling, dry-run safety, session provenance, batch resume/retry/QC behavior, dynamic apparel task count, complete inventory, immutable source hashes, disjoint task paths, missing candidates, 80% selection, and delegation-cap packing.
