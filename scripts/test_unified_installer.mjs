#!/usr/bin/env node
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const temp = fs.mkdtempSync(path.join(os.tmpdir(), "heituz-unified-"));
process.env.HEITUZ_INSTALLER_IMPORT = "1";
const { imggenUpdateArgs, npxInvocation } = await import("./heituz.mjs");
delete process.env.HEITUZ_INSTALLER_IMPORT;

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
  const updateManifest = { imggen2_target: "/tmp/imggen", vision_qc_requested: "auto" };
  const interactiveUpdate = imggenUpdateArgs(updateManifest, { interactive: true });
  assert.deepEqual(interactiveUpdate.slice(-2), ["--vision-qc", "auto"]);
  const automatedUpdate = imggenUpdateArgs(updateManifest, { interactive: false });
  assert.deepEqual(automatedUpdate.slice(-2), ["--vision-qc", "auto"]);
  // Windows cannot spawn npx.cmd without a shell; the invocation must route through cmd.exe /c.
  assert.deepEqual(npxInvocation(true, ["--yes", "pkg"]), { command: "cmd.exe", args: ["/d", "/s", "/c", "npx", "--yes", "pkg"] });
  assert.deepEqual(npxInvocation(false, ["--yes", "pkg"]), { command: "npx", args: ["--yes", "pkg"] });
  const plan = invoke(["scripts/install.mjs", "--dry-run"], { HEITUZ_TEST_PLATFORM: "win32", LOCALAPPDATA: path.join(temp, "local"), APPDATA: path.join(temp, "roaming") });
  assert.match(plan, /powershell\.exe/);
  assert.match(plan, /install\.ps1/);
  assert.match(plan, /HeiTuzMPW/);
  const offlineVisionPlan = JSON.parse(invoke(["scripts/install.mjs", "--dry-run", "--vision-qc", "auto", "--offline"], { HEITUZ_TEST_PLATFORM: "linux" }));
  assert.equal(offlineVisionPlan.vision_qc.requested_mode, "auto");
  assert.equal(offlineVisionPlan.vision_qc.mode, "auto");
  assert.match(offlineVisionPlan.vision_qc.config, /vision-qc\.json$/);

  const target = path.join(temp, "imggen2");
  invoke(["scripts/install.mjs", "--target", target, "--offline", "--register", "--vision-qc", "auto"], { HEITUZ_TEST_PLATFORM: "linux" });
  const manifest = path.join(temp, "config", "heituz", "installation.json");
  const launcher = path.join(temp, ".local", "bin", "heituz");
  assert.equal(fs.existsSync(manifest), true);
  assert.equal(fs.existsSync(launcher), true);
  assert.match(fs.readFileSync(path.join(temp, ".profile"), "utf8"), /heituz user bin/);
  assert.match(fs.readFileSync(path.join(temp, ".zprofile"), "utf8"), /heituz user bin/);
  const visionQcConfig = path.join(target, "vision-qc.json");
  assert.deepEqual(JSON.parse(fs.readFileSync(visionQcConfig, "utf8")), { version: 2, requested_mode: "auto", qc_mode: "auto", reviewer: "host-default-vision" });
  const manifestData = JSON.parse(fs.readFileSync(manifest, "utf8"));
  assert.equal(manifestData.vision_qc_requested, "auto");
  assert.equal(manifestData.vision_qc_mode, "auto");
  const updater = invoke(["update", "--dry-run"], { HEITUZ_TEST_PLATFORM: "linux" }, launcher);
  assert.match(updater, /HeiTuzImgGen2 update/);
  assert.match(updater, /--vision-qc.*auto/);
  assert.match(updater, /HeiTuzMPW update/);
  assert.doesNotMatch(updater, /\/Users\/eusin/);
  const visionQcSetup = invoke(["vision-qc", "setup"], { HEITUZ_TEST_PLATFORM: "linux" }, launcher);
  assert.match(visionQcSetup, /host's default Vision model/);
  const visionQcStatus = invoke(["vision-qc", "status"], { HEITUZ_TEST_PLATFORM: "linux" }, launcher);
  assert.deepEqual(JSON.parse(visionQcStatus), { vision_qc: "auto", reviewer: "host-default-vision" });
  // Offline/test installs without --register must not touch global state.
  const manifestBefore = fs.readFileSync(manifest, "utf8");
  const isolatedTarget = path.join(temp, "imggen2-isolated");
  const isolated = invoke(["scripts/install.mjs", "--target", isolatedTarget, "--offline", "--vision-qc", "off"], { HEITUZ_TEST_PLATFORM: "linux" });
  assert.match(isolated, /not registered/);
  assert.equal(fs.existsSync(path.join(isolatedTarget, "SKILL.md")), true);
  assert.equal(fs.readFileSync(manifest, "utf8"), manifestBefore);

  // A failing Pillow provisioning (e.g. PEP 668 externally-managed Python) must not abort the install.
  const brokenPythonBin = path.join(temp, "broken-python-bin");
  fs.mkdirSync(brokenPythonBin, { recursive: true });
  fs.writeFileSync(path.join(brokenPythonBin, "python3"), "#!/bin/sh\nexit 1\n", { mode: 0o755 });
  const pillowTarget = path.join(temp, "imggen2-pillowless");
  const pillowResult = spawnSync(process.execPath, ["scripts/install.mjs", "--target", pillowTarget, "--skip-codex", "--skip-mpw", "--no-register", "--vision-qc", "off"], {
    cwd: root,
    encoding: "utf8",
    env: { ...process.env, HOME: temp, XDG_CONFIG_HOME: path.join(temp, "config"), HEITUZ_TEST_PLATFORM: "linux", PATH: `${brokenPythonBin}:/usr/bin:/bin` },
  });
  assert.equal(pillowResult.status, 0, pillowResult.stderr || pillowResult.stdout);
  assert.match(pillowResult.stderr, /Pillow could not be installed automatically/);
  assert.equal(fs.existsSync(path.join(pillowTarget, "SKILL.md")), true);

  const windowsTarget = path.join(temp, "windows-imggen2");
  const localAppData = path.join(temp, "local-app-data");
  const appData = path.join(temp, "app-data");
  const windowsBin = path.join(localAppData, "HeiTuz", "bin");
  fs.mkdirSync(windowsBin, { recursive: true });
  fs.writeFileSync(path.join(windowsBin, "heituz"), "stale extensionless launcher");
  fs.writeFileSync(path.join(windowsBin, "heituz.mjs"), "stale mjs launcher");
  invoke(["scripts/install.mjs", "--target", windowsTarget, "--offline", "--register", "--vision-qc", "off"], {
    HEITUZ_TEST_PLATFORM: "win32", LOCALAPPDATA: localAppData, APPDATA: appData,
  });
  const windowsLauncher = path.join(localAppData, "HeiTuz", "bin", "heituz.cmd");
  const windowsPowerShellLauncher = path.join(localAppData, "HeiTuz", "bin", "heituz.ps1");
  assert.equal(fs.existsSync(windowsLauncher), true);
  assert.equal(fs.existsSync(windowsPowerShellLauncher), true);
  assert.match(fs.readFileSync(windowsLauncher, "utf8"), /%APPDATA%\\HeiTuz\\heituz\.mjs/);
  assert.match(fs.readFileSync(windowsPowerShellLauncher, "utf8"), /\$env:APPDATA\\HeiTuz\\heituz\.mjs/);
  assert.equal(fs.existsSync(path.join(windowsBin, "heituz")), false);
  assert.equal(fs.existsSync(path.join(windowsBin, "heituz.mjs")), false);
  assert.equal(fs.existsSync(path.join(appData, "HeiTuz", "installation.json")), true);
  assert.deepEqual(JSON.parse(fs.readFileSync(path.join(windowsTarget, "vision-qc.json"), "utf8")), { version: 2, requested_mode: "off", qc_mode: "off", reviewer: "host-default-vision" });
  console.log("unified install/update dry-run: OK");
} finally {
  fs.rmSync(temp, { recursive: true, force: true });
}
