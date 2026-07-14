# Temporary Image Output and Folder Batch Implementation Plan

> **For Hermes:** Execute this plan with strict TDD and verify on native Windows plus WSL.

**Goal:** Make employee folder-based image jobs easy while ensuring unstored image artifacts do not accumulate on the Hermes PC.

**Architecture:** Add a dedicated OS-temp workspace with a 24-hour default retention policy. Explicit employee/shared-folder destinations are never auto-deleted. Add a folder inventory helper that writes a production JSONL manifest for the existing batch runner, then document Discord delivery and output-routing rules in the skill.

**Tech Stack:** Python 3.11+, pathlib, tempfile, shutil, unittest, existing HeiTuzImgGen2 batch runner.

---

### Task 1: Dedicated temporary output lifecycle

**Files:**
- Create: `scripts/output_lifecycle.py`
- Create: `scripts/test_output_lifecycle.py`
- Modify: `scripts/codex_subscription_transport.py`
- Modify: `scripts/test_codex_subscription_transport.py`

1. Write failing tests for OS-native temp roots, explicit output preservation, old-job cleanup, symlink-safe deletion, and the new default single-image destination.
2. Run the targeted tests and confirm RED.
3. Implement a dedicated `HeiTuzImgGen2` temporary root and 24-hour retention cleanup.
4. Change only the implicit single-image destination; explicit `--output` and `--batch-dir` remain authoritative.
5. Re-run targeted tests and confirm GREEN.

### Task 2: Folder-to-manifest preparation

**Files:**
- Create: `scripts/folder_batch_prepare.py`
- Create: `scripts/test_folder_batch_prepare.py`

1. Write failing tests for recursive image inventory, stable relative PNG output names, original-file preservation, explicit output roots, temporary output roots, empty folders, and output-folder exclusion.
2. Run tests and confirm RED.
3. Implement the smallest helper that snapshots supported source files and writes a valid JSONL manifest using one source image per job.
4. Validate the generated manifest with `codex_subscription_batch.load_manifest`.
5. Re-run tests and confirm GREEN.

### Task 3: Cleanup command and operating contract

**Files:**
- Create: `scripts/cleanup_temp_outputs.py`
- Modify: `SKILL.md`
- Modify: `references/batch-production-contract.md`

1. Add a quiet cleanup CLI suitable for scheduled execution.
2. Document routing: explicit requested folder persists; Discord/local staging uses OS temp; originals are never overwritten; large Discord batches are delivered as an archive plus summary; only paths accessible to the central Hermes host may be used.
3. Document that employee-local `C:\...` paths require an approved employee-PC execution route, while `\\Dint\00.딘트공유\...` is the normal shared path.

### Task 4: Verification and deployment

1. Run targeted tests, the full Python suite, and `py_compile` on native Windows.
2. Run the full Python suite on WSL/Ubuntu.
3. Run `git diff --check` and an independent code review.
4. Install the verified files into the active `HeiTuzImgGen2` skill directory.
5. Register a silent 6-hour cleanup job with a 24-hour retention threshold.
6. Dry-run a sample folder manifest in an isolated temporary directory and verify source/output counts and paths.
