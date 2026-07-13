#!/usr/bin/env node

import { cpSync, existsSync, mkdirSync, realpathSync } from "node:fs";
import { homedir } from "node:os";
import { dirname, join, resolve } from "node:path";
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

mkdirSync(dirname(destination), { recursive: true });
cpSync(source, destination, {
  recursive: true,
  filter(path) {
    const relative = path.slice(source.length);
    return !relative.includes("/.git") && !relative.includes("/node_modules") && !relative.includes("/__pycache__");
  },
});

console.log(`Installed HeiTuzimgGen2 to ${destination}`);
