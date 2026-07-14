#!/usr/bin/env node
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const temp = fs.mkdtempSync(path.join(os.tmpdir(), "heituz-unified-"));

function invoke(args, env = {}, command = process.execPath) {
  const result = spawnSync(command, args, {
    cwd: root,
    encoding: "utf8",
    env: { ...process.env, HOME: temp, XDG_CONFIG_HOME: path.join(temp, "config"), ...env },
  });
  assert.equal(result.status, 0, result.stderr || result.stdout);
  return result.stdout;
}

try {
  const plan = invoke(["scripts/install.mjs", "--dry-run"], { HEITUZ_TEST_PLATFORM: "win32", LOCALAPPDATA: path.join(temp, "local"), APPDATA: path.join(temp, "roaming") });
  assert.match(plan, /powershell\.exe/);
  assert.match(plan, /install\.ps1/);
  assert.match(plan, /HeiTuzMPW/);

  const target = path.join(temp, "imggen2");
  invoke(["scripts/install.mjs", "--target", target, "--offline"], { HEITUZ_TEST_PLATFORM: "linux" });
  const manifest = path.join(temp, "config", "heituz", "installation.json");
  const launcher = path.join(temp, ".local", "bin", "heituz");
  assert.equal(fs.existsSync(manifest), true);
  assert.equal(fs.existsSync(launcher), true);
  const updater = invoke(["update", "--dry-run"], { HEITUZ_TEST_PLATFORM: "linux" }, launcher);
  assert.match(updater, /HeiTuzImgGen2 update/);
  assert.match(updater, /HeiTuzMPW update/);
  assert.doesNotMatch(updater, /\/Users\/eusin/);

  const windowsTarget = path.join(temp, "windows-imggen2");
  const localAppData = path.join(temp, "local-app-data");
  const appData = path.join(temp, "app-data");
  invoke(["scripts/install.mjs", "--target", windowsTarget, "--offline"], {
    HEITUZ_TEST_PLATFORM: "win32", LOCALAPPDATA: localAppData, APPDATA: appData,
  });
  const windowsLauncher = path.join(localAppData, "HeiTuz", "bin", "heituz.cmd");
  assert.equal(fs.existsSync(windowsLauncher), true);
  assert.match(fs.readFileSync(windowsLauncher, "utf8"), /%APPDATA%\\HeiTuz\\heituz\.mjs/);
  assert.equal(fs.existsSync(path.join(appData, "HeiTuz", "installation.json")), true);
  console.log("unified install/update dry-run: OK");
} finally {
  fs.rmSync(temp, { recursive: true, force: true });
}
