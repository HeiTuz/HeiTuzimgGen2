#!/usr/bin/env node

import { copyFileSync, existsSync, lstatSync, mkdirSync, readdirSync, realpathSync } from "node:fs";
import { homedir } from "node:os";
import { basename, dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const source = realpathSync(join(dirname(fileURLToPath(import.meta.url)), ".."));
const args = process.argv.slice(2);
const targetIndex = args.indexOf("--target");
if (targetIndex !== -1 && !args[targetIndex + 1]) {
  console.error("--target requires a directory path");
  process.exit(2);
}
if (args.some((arg, index) => arg.startsWith("-") && index !== targetIndex)) {
  console.error("Usage: heituz-imggen2 [--target DIRECTORY]");
  process.exit(2);
}

const destination = resolve(
  targetIndex === -1
    ? join(homedir(), ".hermes", "skills", "HeiTuzimgGen2")
    : args[targetIndex + 1],
);
if (existsSync(destination)) {
  console.error(`Refusing to overwrite existing installation: ${destination}`);
  process.exit(1);
}

const ALLOWED_ROOTS = new Set(["SKILL.md", "README.md", "LICENSE", "package.json", "references", "scripts"]);
function shouldCopy(rel) {
  const parts = rel.split(/[/\\]/u);
  if (!ALLOWED_ROOTS.has(parts[0])) return false;
  if (parts.some((part) => [".git", ".gjc", ".omx", "node_modules", "docs-internal", "__pycache__"].includes(part))) return false;
  if (basename(rel) === ".DS_Store" || rel.endsWith(".pyc") || rel.endsWith(".bak")) return false;
  return true;
}

function copyTree(current) {
  for (const entry of readdirSync(current)) {
    const from = join(current, entry);
    const rel = relative(source, from);
    if (!shouldCopy(rel)) continue;
    const to = join(destination, rel);
    const stat = lstatSync(from);
    if (stat.isDirectory()) {
      mkdirSync(to, { recursive: true });
      copyTree(from);
    } else if (stat.isFile()) {
      mkdirSync(dirname(to), { recursive: true });
      copyFileSync(from, to, 0);
    }
  }
}

mkdirSync(destination, { recursive: true });
copyTree(source);
if (!existsSync(join(destination, "SKILL.md"))) {
  console.error(`Install verification failed: SKILL.md missing in ${destination}`);
  process.exit(1);
}
console.log(`Installed HeiTuzimgGen2 to ${destination}`);
