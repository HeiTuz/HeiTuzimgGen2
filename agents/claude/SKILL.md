---
name: HeiTuzimgGen2
description: "Generate and edit images through the default official Codex CLI subscription route, with provenance-safe single-image transport, resumable exact-N batches, independent QC, and an optional dynamic apparel full-set workflow. Claude Code host surface: the optional Grok route requires Hermes-native tooling and stays disabled on this host."
version: 1.8.2
author: HeiTuz
license: MIT
platforms: [linux, macos, windows]
metadata:
  host_surface: claude
  canonical_source: "HeiTuz/HeiTuzimgGen2 SKILL.md v1.8.2"
  tags: [image-generation, image-editing, chatgpt]
  category: creative
---

# HeiTuzimgGen2 (Claude Code surface)

> **Host integration — Claude Code.** This file is the entry surface for Claude Code installs (`~/.claude/skills/HeiTuzImgGen2`). The rules below are identical to the canonical SKILL.md; only the host-integration surface (frontmatter, invocation notes, tool naming) is migrated.
> - **Invocation**: Claude Code loads this skill by frontmatter `description` match. `scripts/*.py` commands run through the Bash tool.
> - **Vision QC tool**: the "host's default Vision tool" on this host is Claude's native image understanding — read the artifact with the Read tool and apply the QC rubric below. No separate reviewer model is pinned.
> - **Grok route**: the explicit-only Grok route requires the Hermes-native xAI `image_generate` tool plus `xai-oauth`. Neither exists on Claude Code, so an explicit Grok request always fails closed as `grok_route: disabled` — never substitute Codex or another provider for it.

Generate or edit images through the official Codex CLI with an authenticated ChatGPT subscription. Codex remains the default for every ordinary request. A separate Grok route exists only for a current request that explicitly names `Grok`, `그록`, or `xAI` as the image provider, and only when Hermes has `xai-oauth` plus its native xAI `image_generate` tool. The skill remains a transport and result-QC tool. When `HeiTuzMPW` is installed, it may own final IMAGE prompt compilation and emit the shared portable handoff described below.

## Capabilities

- text-to-image, edits, and two-to-four reference compositions;
- dry-run-first transport with exclusive output creation and session-scoped artifact provenance;
- resumable JSONL batches with a sequential pilot, bounded fan-out, ledger ownership, selective retry, and independent QC reconciliation;
- explicit-only Grok image generation through Hermes native `image_generate`, gated on `xai-oauth`, with exact-N queueing that starts at 3 active jobs and never exceeds 5;
- risk-based post-generation QC through the host's default Vision tool in `auto` mode for reference/edit/product/promo work, with simple text-only generation skipping the visual loop;
- optional apparel full-set preparation: colors stay product metadata while `candidate_attempt_count` independently defaults to three complete candidate attempts, followed by default mixed per-cut selection across attempts at a minimum 80% family-similarity gate; an explicit `selection_mode: whole-set` keeps one coherent candidate set.

Never use API-key billing for image generation, private endpoints, DOM automation, cookie extraction, silent provider fallback, or a model claim not supported by returned evidence. An `XAI_API_KEY` alone never enables the HeiTuz Grok route. Post-generation QC uses the host's currently configured default Vision model; ImgGen2 does not pin a separate reviewer model or provider. Never turn a requested label into an attestation: `observed_model` and `model_identity_attested` stay unset unless supported evidence exists. For delivery, use a supported file attachment; printing the path is not delivery evidence.
Never fall back to a different generation provider or a pinned reviewer model when the configured route fails.

## Boundaries

- A successful transport proves only that an artifact was obtained; it does not prove visual acceptance or a particular model identity.
- An explicit user request to create images authorizes the bounded generation scope. `--execute` runs it without a second confirmation or approval-marker ceremony. Fresh approval is required only for scope/count expansion, provider or paid-route changes, overwriting originals, or external publication/delivery.
- The presence of xAI credentials never changes routing. Bare image and exact-count requests stay on Codex. Grok activates only on explicit provider intent and fails closed as `grok_route: disabled` when `xai-oauth` or the native xAI `image_generate` tool is unavailable.
- Product-photo candidate tasks use the standard ImgGen2 generation backend. Every attempt receives the same complete source inventory, product specification, QC contract, and output inventory while keeping output roots and ledgers disjoint.
- A path from another operating system is not a local file. Never guess `/Users/...` as `C:\\Users\\...` or map a foreign home directory by username. Require file transfer/re-attachment or a real local/UNC path. Only deterministic WSL mount mappings such as `/mnt/c/...` may be converted automatically.
- On Windows, accept drive-letter paths, UNC shares, spaces, Unicode, and local `file://` URIs. Reject reserved device names, trailing dots/spaces, credential-bearing file URIs, and symlink/junction/reparse traversal. Use the standard extended-length prefix for long absolute paths instead of silently relocating them.

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

Both commands remain dry-runs unless `--execute` is supplied. The user's explicit generation request authorizes that bounded invocation; no additional marker is required. See [references/execution-contract.md](references/execution-contract.md).

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

The first cut is always a sequential transport pilot. If that job requires visual QC, bounded fan-out begins only after its independent QC passes. A simple text-only pilot with no references, product-photo correction, promotional layout, or explicit review request skips Vision QC and continues in the same pass. The batch owns an atomic ledger; resume is hash-verified against ledger-owned outputs, and failures become a fresh retry manifest. Parallel workers may only own disjoint output roots and ledgers. `--batch-dir` on the single-image helper is still one image call. Read [references/batch-production-contract.md](references/batch-production-contract.md) before batch work.

For bulk ideation/reference-board requests, use `scripts/creative_batch.py`. It invokes HeiTuzMPW once to compile distinct prompt variations, keeps Vision QC off even for 100+ text-only ideas, stages manifests/ledgers/summaries in a hidden resumable workspace, and publishes only final PNGs. Successful runs delete the workspace; failed or interrupted runs retain it for resume. `examples/batch_100_variations.py` is the reusable cross-platform entrypoint, and the packaged presets in `examples/` (including the ecommerce set: hero, thumbnail, detail close-up, color variants, lifestyle, seasonal banner, bundle, beauty, food, home/living, apparel catalog) are thin text-only wrappers over `examples/preset_runner.py`. These presets never accept reference images and must not be presented as product-photo fidelity work.

### Post-generation Vision QC

`auto` is risk-based, not always-on. Invoke the host's default Vision analysis tool when at least one reference/input image exists, the request edits or corrects an existing image, the work is a product-photo correction or product set, the layout is promotional, or the user explicitly asks for review/comparison. On Hermes this uses `vision_analyze`, which follows the live `auxiliary.vision` configuration instead of pinning a reviewer inside ImgGen2. The full original remains the delivery artifact and is never modified.

For a text-only creation with no reference, edit, product-photo correction, promotional layout, or explicit QC request, skip Vision analysis and regeneration. Still verify the output locally: expected file exists, is non-empty, has the expected image format, and does not overwrite another artifact. Mark this path as `qc_status: skipped` with reason `simple_text_only`.

The installed `vision-qc.json` contains `{version: 2, requested_mode: "auto", qc_mode: "auto", reviewer: "host-default-vision"}` and no credentials. `auto` is the default in interactive and non-interactive installs. `off` is the only alternative and disables visual review even for high-risk cases; local artifact validation still applies.

When QC is required, review the image against the requested brief, source fidelity, text accuracy when applicable, material realism, layout, and cross-image consistency. Require a structured result containing the four axis scores, pass/fail, observed defects, and the smallest regeneration delta. Regenerate only failed required cases and only with the smallest failed-axis delta. The review report records the image hash and dimensions; requested model names are not model-identity evidence.

### Provider routing quick reference

| Request | Route |
| --- | --- |
| Ordinary single image or exact-N batch | Codex subscription default |
| Explicit “Grok/그록/xAI로 생성” with `xai-oauth` and native xAI `image_generate` available | Grok OAuth |
| Explicit Grok request without both gates, including API-key-only | Disabled; no fallback |
| Explicit Higgsfield request | Higgsfield skill; never Grok/Codex fallback |

### Apparel full-set preparation

Vision role records may provide explicit `color_identity` values for `color_front` records. Ordinary product folders may instead omit the role map and use the public naming contract: `f1` front, `b1` back, `cN` alternate/color fronts, `dN` details, and `sN` composite-only sources. Colors and candidate attempts are independent: `candidate_attempt_count` defaults to three complete attempts whether the product has one color or many.

Do not infer visual color names from filenames; auto-mapped `cN` values are stable opaque identities. Back/detail evidence does not add attempts. Every candidate task receives the complete source and output inventory. Default selection is mixed: each output cut independently takes the highest-fidelity candidate across attempts that passes support removal, pure white/no shadow, and no invented detail, with fidelity ties resolving deterministically to the lowest attempt index; the final mixed family must still have every pairwise similarity scored and at or above the 80% gate or selection fails closed. An explicit `selection_mode: whole-set` (contract field, Vision-report field, or `--selection-mode whole-set`) keeps one coherent candidate set; unknown or conflicting modes fail closed. Product originals remain outside the run root and are read-only. After verified selection, disposable `candidate-set-*` work directories are deleted automatically and only `selected/` plus minimal provenance remains; this cleanup requires no extra approval. Provenance records the selection mode, the source task/set, hashes, fidelity, and rejected alternatives per cut. Use the observed delegation ceiling as `--runtime-limit`; any over-cap folder is blocked rather than reduced. See [references/cases/apparel-ghost-cut-folder-batch.md](references/cases/apparel-ghost-cut-folder-batch.md).

## Verification

All verification is network-free:

```bash
python -m unittest discover -s scripts -p 'test_*.py' -v
python -m py_compile scripts/*.py
```

The test suite covers output collision handling, dry-run safety, session provenance, batch resume/retry/QC behavior, explicit-only Grok OAuth routing, API-key-only rejection, exact-N queueing without shrinking, dynamic apparel task count, complete inventory, immutable source hashes, disjoint task paths, missing candidates, mixed per-cut and explicit whole-set 80% selection with deterministic ties, and delegation-cap packing.
