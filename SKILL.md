---
name: HeiTuzimgGen2
description: "Generate and edit images through the official Codex CLI using ChatGPT subscription authentication. Includes provenance-safe single-image transport, resumable JSONL batches, independent QC, and an optional dynamic apparel full-set workflow."
version: 1.5.3
author: HeiTuz
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [image-generation, image-editing, chatgpt]
    category: creative
---

# HeiTuzimgGen2

Generate or edit images through the official Codex CLI with an authenticated ChatGPT subscription. The skill is transport and result-QC infrastructure; `HeiTuzMPW` owns final IMAGE prompt compilation when both are installed.

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

### Production batch

Compile a self-contained prompt per cut, prepare a JSONL manifest, then dry-run:

```bash
python scripts/codex_subscription_batch.py \
  --manifest "$PWD/jobs.jsonl" \
  --output-root "$PWD/product-batch" \
  --workers auto
```

The first cut is a sequential capability-and-quality pilot. Bounded fan-out begins only after independent pilot QC passes. The batch owns an atomic ledger; resume is hash-verified against ledger-owned outputs, and failures become a fresh retry manifest. Hermes subagents may only own disjoint output roots and ledgers. `--batch-dir` on the single-image helper is still one image call. Read [references/batch-production-contract.md](references/batch-production-contract.md) before batch work.

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
