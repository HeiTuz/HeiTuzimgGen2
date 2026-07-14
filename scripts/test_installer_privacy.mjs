#!/usr/bin/env node
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const temp = fs.mkdtempSync(path.join(os.tmpdir(), "heituzimggen2-install-"));

function run(command, args) {
  const result = spawnSync(command, args, { cwd: root, encoding: "utf8" });
  assert.equal(result.status, 0, `${command} failed: ${result.stderr || result.stdout}`);
  return result.stdout;
}

function hasExcludedPath(dir) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const name = entry.name;
    if ([".git", ".gjc", ".omx", "docs-internal", "node_modules", "__pycache__"].includes(name) || name.endsWith(".pyc") || name.includes(".bak")) return true;
    if (entry.isDirectory() && hasExcludedPath(path.join(dir, name))) return true;
  }
  return false;
}

try {
  const destination = path.join(temp, "installed");
  run(process.execPath, ["scripts/install.mjs", "--target", destination, "--offline"]);
  assert.equal(fs.existsSync(path.join(destination, "SKILL.md")), true);
  assert.equal(fs.existsSync(path.join(destination, "contracts", "v1", "image-production-handoff.schema.json")), true);
  assert.equal(hasExcludedPath(destination), false, "installer copied excluded local state");

  const npmCommand = process.platform === "win32" ? "npm.cmd" : "npm";
  const packed = JSON.parse(run(npmCommand, ["pack", "--dry-run", "--json"]));
  const names = packed[0].files.map((file) => file.path);
  assert.equal(names.includes("contracts/v1/image-production-handoff.schema.json"), true,
    "npm package omits the public handoff schema");
  assert.equal(names.some((name) => /(^|\/)(?:\.git|\.gjc|\.omx|docs-internal|node_modules|__pycache__)(?:\/|$)|\.pyc$|\.bak/u.test(name)), false,
    "npm package includes excluded local state");
  console.log("installer/package privacy allowlist: OK");
} finally {
  fs.rmSync(temp, { recursive: true, force: true });
}
