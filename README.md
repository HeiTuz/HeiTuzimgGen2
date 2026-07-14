# HeiTuzimgGen2

**ChatGPT subscription image production with receipts, not wishful thinking.**

HeiTuzimgGen2 uses the official Codex CLI to generate or edit images through an authenticated ChatGPT subscription. It turns image work into a verifiable pipeline: dry-run first, exclusive outputs, session-scoped provenance, bounded batch fan-out, QC gates, and selective retries.

## What ships

- Text-to-image, edits, and two-to-four reference compositions
- No API key or separate image usage account required
- Dry-run validation before live execution
- Hash-owned output and resume protection
- JSONL batch runner with pilot-first fan-out and failed-cut retries
- Independent four-axis and promotional QC reconciliation
- Optional dynamic apparel full-set preparation from Vision role maps

The browser-based apparel executor is intentionally adapter-gated. It is dry-run by default and requires an explicit external browser adapter for a live call; it never silently switches providers.

## Install

Requirements: Python 3.10+, the official `codex` CLI, and an authenticated ChatGPT subscription session.

```bash
npx --yes github:HeiTuz/HeiTuzimgGen2#v1.6.0
# or
bunx github:HeiTuz/HeiTuzimgGen2#v1.6.0
```

Install into a specific directory:

```bash
npx --yes github:HeiTuz/HeiTuzimgGen2#v1.6.0 -- --target "$HOME/.hermes/skills/HeiTuzimgGen2"
```

The forwarded target form also works with Bun:

```bash
bunx github:HeiTuz/HeiTuzimgGen2#v1.6.0 -- --target "$HOME/.hermes/skills/HeiTuzimgGen2"
```

## Start with a dry-run

```bash
python scripts/codex_subscription_transport.py \
  --prompt "A blue ceramic cup on natural linen"
```

Add `--image` once per reference for an edit or composition. A live call requires `--execute` and the current approval marker documented in [references/execution-contract.md](references/execution-contract.md).

## Portable compiler handoff

HeiTuzimgGen2 remains standalone: prompts can be passed directly to the single-image or batch commands above. When [HeiTuzMPW](https://github.com/HeiTuz/HeiTuzMPW) is installed, it can compile an image request into the shared, provider-neutral `heituz-image-production-handoff/v1` JSON contract. Validate and consume that handoff with:

```bash
python scripts/consume_image_handoff.py request.json --output-root "$PWD/generated"
```

The command is dry-run by default and uses the same approval and transport boundary as direct invocation. The shared handoff contains an operation, compiled prompt, portable output basename, up to 20 portable image references, and optional string metadata; it contains no machine routing or credentials. This executor currently accepts up to four local references and a PNG output, failing closed on other valid contract capabilities. The canonical schema is [contracts/v1/image-production-handoff.schema.json](contracts/v1/image-production-handoff.schema.json). HTTPS references validate for interchange but must be materialized as relative local files before execution.

## Batch production

```bash
python scripts/codex_subscription_batch.py \
  --manifest "$PWD/jobs.jsonl" \
  --output-root "$PWD/product-batch" \
  --workers auto
```

The first cut runs alone. Only an independent QC pass opens bounded fan-out. Read [references/batch-production-contract.md](references/batch-production-contract.md) before submitting a live batch.

## Apparel full-set workflow

For product folders, task count is the number of unique normalized `color_identity` values in Vision records labeled `color_front`—not a fixed number and never inferred from filenames. Every task gets the same complete folder and independently creates its entire candidate set. A selector evaluates cross-set combinations against source fidelity and a minimum 80% family-similarity gate.

## Verify

```bash
python -m unittest discover -s scripts -p 'test_*.py' -v
python -m py_compile scripts/*.py
```

The suite is network-free. It covers transport safety, batch recovery, QC gates, dynamic apparel task planning, immutable source inventory, disjoint paths, selection, and runtime-cap packing.

## Security boundary

The skill does not inspect authentication files, extract cookies, call private endpoints, use API-key billing, or expose raw subprocess output in user-facing errors.

## License

MIT © HeiTuz
