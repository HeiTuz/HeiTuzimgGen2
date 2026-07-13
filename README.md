# HeiTuzimgGen2

Generate and edit images through the official Codex CLI using your existing ChatGPT subscription—without an OpenAI API key or separate usage credits.

HeiTuzimgGen2 turns a plain image request into a verified PNG, supports one-image edits and up to four reference images, refuses accidental overwrites, and keeps raw CLI errors out of user-facing output.

## What it does

- Text-to-image generation through Codex `imagegen`
- Edit or restyle an existing image
- Combine two to four reference images
- Default single-image output to `~/Downloads`
- Dated folders for batch workflows
- Dry-run validation before any live generation
- Secret-safe error classification and collision protection

## Install

Requirements: Python 3.10+, the official `codex` CLI, and an authenticated ChatGPT subscription session.

```bash
npx --yes github:HeiTuz/HeiTuzimgGen2
```

Or with Bun:

```bash
bunx github:HeiTuz/HeiTuzimgGen2
```

Manual installation:

```bash
git clone https://github.com/HeiTuz/HeiTuzimgGen2.git
mkdir -p ~/.hermes/skills
cp -R HeiTuzimgGen2 ~/.hermes/skills/HeiTuzimgGen2
```

## Use

Dry-run validation makes no network call:

```bash
python ~/.hermes/skills/HeiTuzimgGen2/scripts/codex_subscription_transport.py \
  --prompt "A blue ceramic cup on natural linen"
```

Edit an existing image:

```bash
python ~/.hermes/skills/HeiTuzimgGen2/scripts/codex_subscription_transport.py \
  --prompt "Keep the subject; change only the background to warm gray" \
  --image "$PWD/input.png" \
  --output "$PWD/output/edited.png"
```

Live generation is intentionally gated. Review `references/execution-contract.md` before using `--execute`.

## Verify

```bash
python -m unittest discover -s scripts -p 'test_*.py' -v
```

The test suite is local and network-free.

## Security boundaries

HeiTuzimgGen2 does not read Codex authentication files, extract browser cookies, call private endpoints, or fall back to API-key billing. Raw subprocess output is withheld from user-facing errors because it may contain session data.

## License

MIT © HeiTuz
