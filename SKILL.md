---
name: HeiTuzimgGen2
description: "Generate and edit images through the default official Codex CLI subscription route, with an explicit-only optional Grok route gated on Hermes xAI OAuth. Includes provenance-safe single-image transport, resumable exact-N batches, independent QC, and an optional dynamic apparel full-set workflow."
version: 1.7.0
author: HeiTuz
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [image-generation, image-editing, chatgpt]
    category: creative
---

# HeiTuzimgGen2

Generate or edit images through the official Codex CLI with an authenticated ChatGPT subscription. Codex remains the default for every ordinary request. A separate Grok route exists only for a current request that explicitly names `Grok`, `그록`, or `xAI` as the image provider, and only when Hermes has `xai-oauth` plus its native xAI `image_generate` tool. The skill remains a transport and result-QC tool. When `HeiTuzMPW` is installed, it may own final IMAGE prompt compilation and emit the shared portable handoff described below.

## Capabilities

- text-to-image, edits, and two-to-four reference compositions;
- dry-run-first transport with exclusive output creation and session-scoped artifact provenance;
- resumable JSONL batches with a sequential pilot, bounded fan-out, ledger ownership, selective retry, and independent QC reconciliation;
- explicit-only Grok image generation through Hermes native `image_generate`, gated on `xai-oauth`, with exact-N queueing that starts at 3 active jobs and never exceeds 5;
- required post-generation Gemini/Luna image QC before `vision_analyze`, with thumbnail-only review, strict structured output, and provenance-bound reports;
- optional apparel full-set preparation: one complete candidate set per unique normalized `color_identity` from Vision `color_front` records, followed by cross-set selection at a minimum 80% family-similarity gate.

Never use API-key billing for image generation, private endpoints, DOM automation, cookie extraction, silent provider fallback, or a model claim not supported by returned evidence. An `XAI_API_KEY` alone never enables the HeiTuz Grok route. The post-generation QC exception may use the preconfigured Google Gemini Developer API key for `gemini-3-flash-preview`; its only fallback is exactly one `gpt-5.6-luna` Codex-subscription review after a Gemini timeout, HTTP 429, or HTTP 5xx. Hard 4xx and malformed responses fail closed. Never fall back outside those explicit contracts. never turn a requested label into an attestation: `observed_model` and `model_identity_attested` stay unset unless supported evidence exists. For delivery, use `send_message` with a document/file attachment; printing the path is not delivery evidence.

## Boundaries

- A successful transport proves only that an artifact was obtained; it does not prove visual acceptance or a particular model identity.
- Live image execution requires a fresh approval marker immediately before `--execute`.
- The presence of xAI credentials never changes routing. Bare image and exact-count requests stay on Codex. Grok activates only on explicit provider intent and fails closed as `grok_route: disabled` when `xai-oauth` or the native xAI `image_generate` tool is unavailable.
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

### Explicit Grok OAuth route

Use Grok only when the current request explicitly says to generate or edit the image with `Grok`, `그록`, or `xAI`. Require a configured Hermes `xai-oauth` credential and the Hermes-native xAI `image_generate` tool in the current session. API-key-only environments do not qualify. If either gate is absent, stop without login, token inspection, or fallback.

Do not invoke Grok through `hermes chat`, `progrok`, browser cookies, or a new private API client. A single request calls native `image_generate` once. An exact-N request creates N independent jobs, runs one pilot through local materialization, hash verification, and QC, then fans out from 3 active jobs to a maximum of 5 while queueing the remainder. Failed-job-only retries never overwrite or repeat verified successes. Full contract: [references/grok-oauth-explicit-routing.md](references/grok-oauth-explicit-routing.md).

### Portable compiled handoff

Direct prompt invocation remains fully supported and does not require another skill. An installed `HeiTuzMPW` compiler may instead emit `heituz-image-production-handoff/v1` JSON. Consume it without host-specific routing:

```bash
python scripts/consume_image_handoff.py request.json \
  --output-root "$PWD/generated"
```

This adapter validates [contracts/v1/image-production-handoff.schema.json](contracts/v1/image-production-handoff.schema.json), resolves relative input paths from the handoff file, keeps the output under `--output-root`, and delegates to the same dry-run-first transport. HTTPS input references must first be materialized as relative local files. The handoff must never contain credentials, approval state, session identifiers, or machine/worker routing.

### Production batch

Compile a self-contained prompt per cut, prepare a JSONL manifest, then dry-run:

```bash
python scripts/codex_subscription_batch.py \
  --manifest "$PWD/jobs.jsonl" \
  --output-root "$PWD/product-batch" \
  --workers auto
```

The first cut is a sequential capability-and-quality pilot. Bounded fan-out begins only after independent pilot QC passes. The batch owns an atomic ledger; resume is hash-verified against ledger-owned outputs, and failures become a fresh retry manifest. Parallel workers may only own disjoint output roots and ledgers. `--batch-dir` on the single-image helper is still one image call. Read [references/batch-production-contract.md](references/batch-production-contract.md) before batch work.

### Post-generation Gemini/Luna image QC

Run `gemini_image_qc.py` for every generated delivery candidate **before** `vision_analyze`. The full original remains the delivery artifact and is never uploaded or modified. QC uses only an ephemeral JPEG thumbnail with a 1024 px long-edge limit and a 300 KiB cap.

The installed `vision-qc.json` contains only `{version, requested_mode, qc_mode}` and never credentials. `auto` resolves to `gemini-luna` when both a Gemini key and Codex are available, `gemini` when only a key is available, `luna` when only Codex is available, and `off` otherwise. `gemini-luna` permits the bounded Luna fallback, `gemini` never falls back, `luna` uses direct Codex-subscription review, and `off` blocks QC fail-closed. `--qc-mode` overrides `HEITUZ_VISION_QC_MODE`, which overrides the installed mode; every resolved mode is included in its approval hash. `heituz vision-qc setup` displays safe session-only credential setup.
Gemini uses `gemini-3-flash-preview` with the key only in `x-goog-api-key`; a Gemini timeout, HTTP 429, or HTTP 5xx permits exactly one Luna retry. Hard 4xx and malformed Gemini responses fail closed. The dry-run `request_sha256` includes the resolved QC mode and must be supplied in `HERMES_GEMINI_IMAGE_QC_APPROVAL_SHA256` immediately before `--execute`.

```bash
python scripts/gemini_image_qc.py output.png \
  --brief "Source-faithful product image on a clean white background" \
  --expected-text "Navy Essential Tee" \
  --id navy-front

HERMES_GEMINI_IMAGE_QC_APPROVAL_SHA256="<dry-run request_sha256>" \
python scripts/gemini_image_qc.py output.png \
  --brief "Source-faithful product image on a clean white background" \
  --expected-text "Navy Essential Tee" \
  --id navy-front --execute
```

The one-line report records the selected route, requested primary/fallback models, original and thumbnail dimensions/bytes/hashes, standard four-axis QC, and observations. Requested model names are not model-identity evidence; `model_identity_attested` remains false.

### Provider routing quick reference

| Request | Route |
| --- | --- |
| Ordinary single image or exact-N batch | Codex subscription default |
| Explicit “Grok/그록/xAI로 생성” with `xai-oauth` and native xAI `image_generate` available | Grok OAuth |
| Explicit Grok request without both gates, including API-key-only | Disabled; no fallback |
| Explicit Higgsfield request | Higgsfield skill; never Grok/Codex fallback |

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

The test suite covers output collision handling, dry-run safety, session provenance, batch resume/retry/QC behavior, explicit-only Grok OAuth routing, API-key-only rejection, exact-N queueing without shrinking, dynamic apparel task count, complete inventory, immutable source hashes, disjoint task paths, missing candidates, 80% selection, and delegation-cap packing.
