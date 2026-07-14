#!/usr/bin/env node

import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { spawnSync } from "node:child_process";

const source = fs.realpathSync(path.join(path.dirname(fileURLToPath(import.meta.url)), ".."));
const args = process.argv.slice(2).filter((arg, index) => !(index === 0 && arg === "--"));
const ALLOWED_ROOTS = new Set(["SKILL.md", "README.md", "LICENSE", "package.json", "contracts", "references", "scripts"]);

function usage(code = 0) {
  const out = code === 0 ? console.log : console.error;
  out(`HeiTuzImgGen2 unified installer

Usage:
  npx --yes github:HeiTuz/HeiTuzImgGen2 -- [options]
  bunx github:HeiTuz/HeiTuzImgGen2 -- [options]

Options:
  --target <directory>   ImgGen2 installation directory (default: ~/.hermes/skills/HeiTuzImgGen2)
  --mpw-target <dir>     HeiTuzMPW installation directory
  --force                Replace an existing ImgGen2 destination
  --skip-codex           Do not install/update the official Codex CLI
  --skip-mpw             Do not install/update HeiTuzMPW
  --dry-run              Print the platform plan without writing or downloading
  --offline              Local-copy mode for tests; implies --skip-codex and --skip-mpw
  -h, --help             Show this help

After install: heituz update [--dry-run] [--codex]
`);
  process.exit(code);
}

function parse(argv) {
  const options = { target: null, mpwTarget: null, force: false, skipCodex: false, skipMpw: false, dryRun: false, offline: false };
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === "-h" || arg === "--help") usage(0);
    if (arg === "--force") { options.force = true; continue; }
    if (arg === "--skip-codex") { options.skipCodex = true; continue; }
    if (arg === "--skip-mpw") { options.skipMpw = true; continue; }
    if (arg === "--dry-run") { options.dryRun = true; continue; }
    if (arg === "--offline") { options.offline = true; continue; }
    if (arg === "--target" || arg === "--mpw-target") {
      const value = argv[++i];
      if (!value) usage(2);
      options[arg === "--target" ? "target" : "mpwTarget"] = value;
      continue;
    }
    if (arg.startsWith("--target=")) { options.target = arg.slice("--target=".length); continue; }
    if (arg.startsWith("--mpw-target=")) { options.mpwTarget = arg.slice("--mpw-target=".length); continue; }
    usage(2);
  }
  if (options.offline) { options.skipCodex = true; options.skipMpw = true; }
  return options;
}

function shouldCopy(rel) {
  const parts = rel.split(/[/\\]/u);
  if (!ALLOWED_ROOTS.has(parts[0])) return false;
  return !parts.some((part) => [".git", ".gjc", ".omx", "node_modules", "docs-internal", "__pycache__"].includes(part)) &&
    !path.basename(rel).startsWith(".") && !rel.endsWith(".pyc") && !rel.endsWith(".bak");
}

function copyTree(current, destination) {
  for (const entry of fs.readdirSync(current)) {
    const from = path.join(current, entry);
    const rel = path.relative(source, from);
    if (!shouldCopy(rel)) continue;
    const to = path.join(destination, rel);
    const stat = fs.lstatSync(from);
    if (stat.isDirectory()) {
      fs.mkdirSync(to, { recursive: true });
      copyTree(from, destination);
    } else if (stat.isFile()) {
      fs.mkdirSync(path.dirname(to), { recursive: true });
      fs.copyFileSync(from, to, fs.constants.COPYFILE_EXCL);
      fs.chmodSync(to, stat.mode & 0o777);
    }
  }
}

function run(command, commandArgs, { dryRun, label }) {
  if (dryRun) { console.log(`[dry-run] ${label}: ${[command, ...commandArgs].map(JSON.stringify).join(" ")}`); return; }
  const result = spawnSync(command, commandArgs, { stdio: "inherit" });
  if (result.error || result.status !== 0) throw new Error(`${label} failed${result.error ? `: ${result.error.message}` : ` (exit ${result.status})`}`);
}

async function main() {
  const options = parse(args);
  process.env.HEITUZ_INSTALLER_IMPORT = "1";
  const helper = await import(pathToFileURL(path.join(source, "scripts", "heituz.mjs")).href);
  delete process.env.HEITUZ_INSTALLER_IMPORT;
  const loc = helper.locations();
  const destination = path.resolve(options.target || path.join(loc.home, ".hermes", "skills", "HeiTuzImgGen2"));
  const mpwTarget = path.resolve(options.mpwTarget || path.join(loc.home, ".hermes", "skills", "prompt-writing", "HeiTuzMPW"));

  if (options.dryRun) {
    console.log(JSON.stringify({ imggen2_target: destination, mpw_target: mpwTarget, codex: helper.codexInstallCommand(loc.windows), platform: loc.windows ? "windows" : "posix" }, null, 2));
    return;
  }
  if (fs.existsSync(destination)) {
    if (!options.force) throw new Error(`Refusing to overwrite existing installation: ${destination}; rerun with --force.`);
    fs.rmSync(destination, { recursive: true, force: true });
  }
  fs.mkdirSync(destination, { recursive: true });
  copyTree(source, destination);
  if (!fs.existsSync(path.join(destination, "SKILL.md"))) throw new Error(`Install verification failed: SKILL.md missing in ${destination}`);

  if (!options.skipCodex && !helper.codexExists(loc.windows)) {
    const plan = helper.codexInstallCommand(loc.windows);
    run(plan.command, plan.args, { dryRun: false, label: "official Codex CLI install" });
  }
  if (!options.skipMpw) {
    run(loc.windows ? "npx.cmd" : "npx", ["--yes", "github:HeiTuz/HeiTuzMPW", "--", "--dest", mpwTarget, "--force", "--quiet"], { dryRun: false, label: "HeiTuzMPW install" });
  }

  fs.mkdirSync(loc.config, { recursive: true });
  fs.copyFileSync(path.join(destination, "scripts", "heituz.mjs"), path.join(loc.config, "heituz.mjs"));
  fs.writeFileSync(loc.manifest, JSON.stringify({ version: 1, imggen2_target: destination, mpw_target: mpwTarget, imggen2_repo: "github:HeiTuz/HeiTuzImgGen2", mpw_repo: "github:HeiTuz/HeiTuzMPW" }, null, 2) + "\n", { mode: 0o600 });
  fs.mkdirSync(loc.bin, { recursive: true });
  if (loc.windows) {
    const launcher = path.join(loc.bin, "heituz.cmd");
    fs.writeFileSync(launcher, `@echo off\r\nnode "%APPDATA%\\HeiTuz\\heituz.mjs" %*\r\n`);
    console.log(`Installed HeiTuzImgGen2 to ${destination}`);
    console.log(`Run ${launcher} update, or add ${loc.bin} to your user PATH once to use heituz everywhere.`);
  } else {
    const launcher = path.join(loc.bin, "heituz");
    fs.writeFileSync(launcher, `#!/bin/sh\nexec node "${path.join(loc.config, "heituz.mjs")}" "$@"\n`, { mode: 0o755 });
    fs.chmodSync(launcher, 0o755);
    const zprofile = path.join(loc.home, ".zprofile");
    const begin = "# >>> heituz user bin >>>";
    const end = "# <<< heituz user bin <<<";
    const existing = fs.existsSync(zprofile) ? fs.readFileSync(zprofile, "utf8") : "";
    if (!existing.includes(begin)) fs.appendFileSync(zprofile, `${existing.endsWith("\n") || !existing ? "" : "\n"}${begin}\nexport PATH="$HOME/.local/bin:$PATH"\n${end}\n`);
    console.log(`Installed HeiTuzImgGen2 to ${destination}`);
    console.log(`Open a new terminal, then run: heituz update`);
  }
}

main().catch((error) => { console.error(`HeiTuzImgGen2 installer: ${error.message}`); process.exitCode = 1; });
