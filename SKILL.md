---
name: HeiTuzimgGen2
description: "Generate or edit images through the official Codex CLI using ChatGPT subscription auth—no API key or usage credits required. Supports text-to-image, single-image edits, and combining up to four references. Single outputs default to ~/Downloads; folder batches use --batch-dir with a dated subfolder."
version: 1.1.0
author: HeiTuz
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [image-generation, image-editing, chatgpt]
    category: creative
---

# HeiTuzimgGen2

This skill generates or edits one image through the official Codex CLI using the user's ChatGPT subscription. It does not attest that a particular image model produced an output unless the supported CLI returns verifiable model evidence.

## When to Use

Use this skill for:

- text-to-image generation;
- editing or restyling one existing image;
- combining two to four reference images;
- returning the finished file to a Telegram conversation as a document.

Do not use it for API-key billing, private endpoints, browser or DOM automation, cookie extraction, or an unapproved provider/model fallback.

## Prerequisites

- The official `codex` CLI must already be installed and authenticated for a ChatGPT subscription.
- Do not inspect, copy, print, or modify Codex authentication files.
- Do not initiate login, logout, OAuth, or account changes from this skill.
- The output directory and every reference image must already exist.

If authentication is unavailable or rejected, stop with a secret-safe error. Never fall back to an OpenAI API key or another provider.

## How to Run

The helper is dry-run by default and makes no network call. Output location follows a two-mode rule:

- **Single generation** (no `--output`, no `--batch-dir`): saved to `~/Downloads/<slug>-<timestamp>.png`.
- **Folder-based batch work**: pass `--batch-dir DIR`; outputs go to a dated subfolder `DIR/YYYYMMDD/<slug>-<timestamp>.png`.
- **Explicit path**: pass `--output PATH` to override both defaults. `--output` and `--batch-dir` are mutually exclusive.

```bash
# Single generation → ~/Downloads
python ~/.hermes/skills/HeiTuzimgGen2/scripts/codex_subscription_transport.py \
  --prompt "A blue ceramic cup on linen"

# Folder-based batch → <folder>/YYYYMMDD/
python ~/.hermes/skills/HeiTuzimgGen2/scripts/codex_subscription_transport.py \
  --prompt "A blue ceramic cup on linen" \
  --batch-dir "$PWD/product-batch"
```

For an edit, repeat `--image` once per reference:

```bash
python ~/.hermes/skills/HeiTuzimgGen2/scripts/codex_subscription_transport.py \
  --prompt "Keep the subject; change only the background to warm gray" \
  --image "$PWD/input.png" \
  --output "$PWD/output/edited.png"
```

A live invocation requires both `--execute` and the fresh approval marker described in `references/execution-contract.md`. Stop and request approval immediately before that first live action. A prior general request to create an image is not the fresh approval marker.

## Quick Reference

| Need | Invocation |
| --- | --- |
| Generate (default → ~/Downloads) | `--prompt TEXT` |
| Batch (folder subfolder) | `--prompt TEXT --batch-dir DIR` |
| Explicit path | `--prompt TEXT --output PATH` |
| Edit | add one `--image PATH` |
| Combine references | add two to four `--image PATH` arguments |
| Validate only | omit `--execute` |
| Live generation | fresh approval, then `HERMES_IMAGE_LIVE_APPROVED=1 ... --execute` |

Outputs are PNG. Codex first writes the artifact under `~/.codex/generated_images/<session_id>/`; the helper verifies a newly created PNG and copies it to the requested output path. Existing outputs are never overwritten.

## Procedure

1. Resolve all input and output paths before execution.
2. Confirm there are zero to four reference images and each is a regular file.
3. Run the helper without `--execute` and inspect its JSON request summary.
4. Confirm `transport` is `official-codex-cli-subscription`, reasoning is `medium`, and `model_identity_attested` is `false` unless supported evidence exists.
5. For a live image, stop and request approval immediately before the call.
6. After approval, make exactly one invocation with the approval marker and `--execute`.
7. Verify the copied output exists and is non-empty; retain `source_artifact` as provenance.
8. Describe the route as the official Codex CLI ChatGPT-subscription path. Codex selects the supported image model; never turn a requested label into an attestation or infer exact model identity from the agent model or filename.
9. In Telegram, send the resulting image with `send_message` as a document/file attachment, preserving the original filename. Do not send a local path as plain text and call that delivery.

## Pitfalls

- The skill name is a routing label, not proof that GPT Image 2 served an output.
- `requested_model` remains `null` because forcing the agent model can break Codex imagegen routing. Only supported response evidence can establish `observed_model`.
- Never retry with another model, provider, API endpoint, API key, browser session, or private backend without explicit authorization.
- Never expose subprocess stdout/stderr on errors; it may contain account or session data.
- Do not overwrite an existing output, create missing reference files, or accept more than four references.
- Do not make a Vision call or Telegram call while validating this installation.

## Verification

Run the local, network-free suite:

```bash
python -m unittest discover \
  -s ~/.hermes/skills/HeiTuzimgGen2/scripts \
  -p 'test_*.py' -v
```

Then run one dry-run and inspect the JSON. Verification must not set `HERMES_IMAGE_LIVE_APPROVED`, pass `--execute`, invoke Vision, or contact Telegram.
