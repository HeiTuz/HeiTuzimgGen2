#!/usr/bin/env node
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";

const script = path.join(path.resolve(path.dirname(fileURLToPath(import.meta.url)), ".."), "scripts", "vision_qc_setup.mjs");

function invoke(args = [], env = {}) {
  const result = spawnSync(process.execPath, [script, ...args], {
    encoding: "utf8",
    env: { ...process.env, GOOGLE_API_KEY: "", GEMINI_API_KEY: "", ...env },
  });
  return result;
}

const posix = invoke([], { HEITUZ_TEST_PLATFORM: "darwin" });
assert.equal(posix.status, 0, posix.stderr);
assert.match(posix.stdout, /macOS\/Linux/);
assert.match(posix.stdout, /stty -echo/);
assert.match(posix.stdout, /GOOGLE_API_KEY/);
assert.doesNotMatch(posix.stdout, /GEMINI_API_KEY/);

const windows = invoke([], { HEITUZ_TEST_PLATFORM: "win32" });
assert.equal(windows.status, 0, windows.stderr);
assert.match(windows.stdout, /Windows PowerShell/);
assert.match(windows.stdout, /Read-Host/);
assert.match(windows.stdout, /ZeroFreeBSTR/);
assert.doesNotMatch(windows.stdout, /stty -echo/);

const secret = "vision-qc-test-secret";
const configured = invoke(["--status"], { GOOGLE_API_KEY: secret });
assert.equal(configured.status, 0, configured.stderr);
assert.deepEqual(JSON.parse(configured.stdout), { vision_qc: "configured", api_key_environment: "GOOGLE_API_KEY" });
assert.doesNotMatch(configured.stdout, new RegExp(secret));

const missing = invoke(["--status"]);
assert.equal(missing.status, 0, missing.stderr);
assert.deepEqual(JSON.parse(missing.stdout), { vision_qc: "needs_api_key", api_key_environment: null });

const invalid = invoke(["--write-key"]);
assert.equal(invalid.status, 2);

console.log("Vision-QC setup: OK");
