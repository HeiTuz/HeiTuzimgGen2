# Browser GPT Apparel Full-Set Selector

## Contract

Use this branch for an apparel product folder that needs independent complete candidate attempts followed by Vision whole-set selection.

Product colors and candidate attempts are independent:

- `color_identity` values are normalized with Unicode NFKC, collapsed whitespace, and case folding;
- `candidate_attempt_count` controls generation attempts and defaults to `3`;
- one or many product colors still produce three complete attempts unless explicitly overridden;
- back and detail evidence never changes the attempt count.

An explicit Vision role map remains supported. Ordinary folders may omit it and use `f1` front, `b1` back, `cN` alternate/color fronts, `dN` details, and `sN` composite-only sources. Auto-mapped `cN` identities are opaque identities, not inferred visual color names.

## Prepare

```bash
python scripts/apparel_three_fullset.py prepare \
  --contract /path/to/folder-contract.json \
  --run-root /path/to/non-source-output-root \
  --runtime-limit 20
```

Preparation hashes the immutable complete source inventory and creates `task-N` → `candidate-set-N/` for each attempt. Every task receives the same originals, role map, folder master, QC contract, and complete output inventory. Candidate roots, browser sessions, ledgers, and provenance remain disjoint. The source folder is read-only and may not overlap the run root.

The scheduler packs whole folders without shrinking attempts. If a folder exceeds `--runtime-limit`, it is blocked rather than silently reduced.

## Execution and retry

Browser execution is dry-run first and requires the configured external adapter plus the existing approval gate. Each attempt uploads only originals and the immutable contract. Generated results are never used as inputs. The batch path retains sequential pilot, independent QC, bounded fan-out, failed-item retry, and ledger-bound resume.

## Whole-set selection

Vision evaluates every complete candidate set for source fidelity, support removal, pure white/no shadow, no invented detail, and pairwise family similarity. Selection is **whole-set only**: cuts from different attempts are never mixed. A set must clear the `80%` family-similarity gate.

`selected/` is staged and atomically renamed. `selected/provenance.json` records source task, candidate set, path, hash, score, and rejected alternatives. Missing or altered ledger-owned outputs fail closed.

## Verification

```bash
python -m unittest discover -s scripts -p 'test_*.py' -v
python -m py_compile scripts/*.py
```
