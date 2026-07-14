#!/usr/bin/env node
import assert from "node:assert/strict";
import { normalizeInstallerPath } from "./install.mjs";

assert.throws(
  () => normalizeInstallerPath("/Users/alice/.hermes/skills/HeiTuzImgGen2", "win32", "C:\\work"),
  /belongs to macOS/u,
);
assert.throws(
  () => normalizeInstallerPath("/home/alice/HeiTuzImgGen2", "win32", "C:\\work"),
  /POSIX syntax/u,
);
assert.throws(
  () => normalizeInstallerPath("C:\\Users\\alice\\HeiTuzImgGen2", "darwin", "/tmp"),
  /belongs to Windows/u,
);
assert.equal(
  normalizeInstallerPath("/mnt/c/Users/alice/HeiTuzImgGen2", "win32", "C:\\work"),
  "C:\\Users\\alice\\HeiTuzImgGen2",
);
assert.equal(
  normalizeInstallerPath("file:///C:/Users/Alice/My%20Skills/HeiTuzImgGen2", "win32", "C:\\work"),
  "C:\\Users\\Alice\\My Skills\\HeiTuzImgGen2",
);
assert.equal(
  normalizeInstallerPath("file://server/share/HeiTuzImgGen2", "win32", "C:\\work"),
  "\\\\server\\share\\HeiTuzImgGen2",
);
const longPath = `C:\\work\\${"nested\\".repeat(40)}HeiTuzImgGen2`;
assert.match(normalizeInstallerPath(longPath, "win32", "C:\\work"), /^\\\\\?\\C:\\/u);

console.log("Windows and cross-OS installer paths: OK");
