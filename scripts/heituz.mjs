#!/usr/bin/env node

import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";

const IMGGEN_REPO = "github:HeiTuz/HeiTuzImgGen2";
const MPW_REPO = "github:HeiTuz/HeiTuzMPW";

function platform() {
  return process.env.HEITUZ_TEST_PLATFORM || process.platform;
}

export function locations() {
  const home = os.homedir();
  const windows = platform() === "win32";
  const config = windows
    ? path.join(process.env.APPDATA || path.join(home, "AppData", "Roaming"), "HeiTuz")
    : path.join(process.env.XDG_CONFIG_HOME || path.join(home, ".config"), "heituz");
  const bin = windows ? path.join(process.env.LOCALAPPDATA || path.join(home, "AppData", "Local"), "HeiTuz", "bin") : path.join(home, ".local", "bin");
  return { home, windows, config, bin, manifest: path.join(config, "installation.json") };
}

export function npxInvocation(windows, args) {
  // Windows cannot spawn npx.cmd directly without a shell (Node rejects .cmd
  // spawns with EINVAL since the April 2024 security release); route through
  // cmd.exe /c with an argument vector instead of shell string interpolation.
  return windows
    ? { command: "cmd.exe", args: ["/d", "/s", "/c", "npx", ...args] }
    : { command: "npx", args };
}

export function codexExists(windows) {
  const home = os.homedir();
  const installDir = process.env.CODEX_INSTALL_DIR;
  const canonical = windows
    ? path.join(process.env.LOCALAPPDATA || path.join(home, "AppData", "Local"), "Programs", "OpenAI", "Codex", "bin", "codex.exe")
    : path.join(home, ".local", "bin", "codex");
  const configured = installDir ? path.join(installDir, windows ? "codex.exe" : "codex") : null;
  return [configured, canonical].filter(Boolean).some((candidate) => fs.existsSync(candidate));
}

export function codexInstallCommand(windows) {
  return windows
    ? { command: "powershell.exe", args: ["-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", "irm https://chatgpt.com/codex/install.ps1 | iex"] }
    : { command: "sh", args: ["-c", "curl -fsSL https://chatgpt.com/codex/install.sh | sh"] };
}

function run(command, args, { dryRun = false, label }) {
  const rendered = [command, ...args].map((part) => JSON.stringify(part)).join(" ");
  if (dryRun) {
    console.log(`[dry-run] ${label}: ${rendered}`);
    return;
  }
  const result = spawnSync(command, args, { stdio: "inherit" });
  if (result.error || result.status !== 0) {
    throw new Error(`${label} failed${result.error ? `: ${result.error.message}` : ` (exit ${result.status})`}`);
  }
}

function usage(code = 0) {
  const out = code === 0 ? console.log : console.error;
  out(`HeiTuz unified updater

Usage:
  heituz update [--dry-run] [--codex]
  heituz status
  heituz vision-qc setup
  heituz vision-qc status

Commands:
  update       Refresh HeiTuzImgGen2 and HeiTuzMPW from their canonical GitHub repositories.
               Codex updates only when missing or when --codex is supplied.
  status       Print the recorded installation targets.
  vision-qc    Show the host-default Vision QC mode or setup guidance.
`);
  process.exit(code);
}

export function imggenUpdateArgs(manifest, { interactive }) {
  const args = ["--yes", IMGGEN_REPO, "--"];
  if (manifest.agent_host) args.push("--agent", manifest.agent_host);
  args.push("--target", manifest.imggen2_target, "--mpw-target", manifest.mpw_target, "--force", "--skip-mpw", "--skip-codex", "--no-register");
  const previous = manifest.vision_qc_requested || manifest.vision_qc_mode;
  const visionQc = previous === "off" ? "off" : "auto";
  args.push("--vision-qc", visionQc);
  return args;
}

export function manifestInstallations(manifest) {
  if (Array.isArray(manifest.installations) && manifest.installations.length) {
    return manifest.installations.map((installation) => ({ ...manifest, ...installation, installations: undefined }));
  }
  return [manifest];
}

export function update(manifest, { dryRun, forceCodex, interactive = Boolean(process.stdin.isTTY && process.stdout.isTTY) }) {
  const { windows } = locations();
  const installations = manifestInstallations(manifest);
  if (installations.some((installation) => !installation.imggen2_target || !installation.mpw_target)) {
    throw new Error("Installation manifest is incomplete; rerun the HeiTuzImgGen2 installer.");
  }
  if (forceCodex || !codexExists(windows)) {
    const plan = codexInstallCommand(windows);
    run(plan.command, plan.args, { dryRun, label: "official Codex CLI install/update" });
  }
  for (const installation of installations) {
    const hostLabel = installation.agent_host ? ` (${installation.agent_host})` : "";
    const imggen = npxInvocation(windows, imggenUpdateArgs(installation, { interactive }));
    run(imggen.command, imggen.args, { dryRun, label: `HeiTuzImgGen2 update${hostLabel}` });
    const mpwArgs = ["--yes", MPW_REPO, "--"];
    if (installation.agent_host) mpwArgs.push("--target", installation.agent_host);
    mpwArgs.push("--dest", installation.mpw_target, "--force", "--quiet");
    const mpw = npxInvocation(windows, mpwArgs);
    run(mpw.command, mpw.args, { dryRun, label: `HeiTuzMPW update${hostLabel}` });
  }
}

function main(argv) {
  const command = argv[0] || "help";
  const flags = new Set(argv.slice(1));
  if (command === "help" || command === "--help" || command === "-h") usage(0);
  const { manifest } = locations();
  if (!fs.existsSync(manifest)) throw new Error(`HeiTuz installation manifest is missing: ${manifest}`);
  const data = JSON.parse(fs.readFileSync(manifest, "utf8"));
  if (command === "status") {
    console.log(JSON.stringify({ ...data, codex_present: codexExists(locations().windows) }, null, 2));
    return;
  }
  if (command === "vision-qc") {
    const action = argv[1] || "setup";
    if (!new Set(["setup", "status"]).has(action) || argv.length !== 2) usage(2);
    const setup = path.join(data.imggen2_target, "scripts", "vision_qc_setup.mjs");
    if (!fs.existsSync(setup)) throw new Error("Vision-QC setup is unavailable; run heituz update.");
    run(process.execPath, [setup, ...(action === "status" ? ["--status"] : [])], { label: "Vision-QC setup" });
    return;
  }
  if (command !== "update") usage(2);
  for (const flag of flags) {
    if (!new Set(["--dry-run", "--codex"]).has(flag)) usage(2);
  }
  update(data, { dryRun: flags.has("--dry-run"), forceCodex: flags.has("--codex") });
  if (!flags.has("--dry-run")) console.log("HeiTuzImgGen2 and HeiTuzMPW are updated.");
}

if (!process.env.HEITUZ_INSTALLER_IMPORT) {
  try {
    main(process.argv.slice(2));
  } catch (error) {
    console.error(`heituz: ${error.message}`);
    process.exitCode = 1;
  }
}
