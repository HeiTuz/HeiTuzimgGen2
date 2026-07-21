#!/usr/bin/env node
import assert from "node:assert/strict";
import { normalizeInstallerPath } from "./install.mjs";

assert.throws(
  () => normalizeInstallerPath("/Users/alice/.hermes/skills/ImgGen2", "win32", "C:\\work"),
  /belongs to macOS/u,
);
assert.throws(
  () => normalizeInstallerPath("/home/alice/ImgGen2", "win32", "C:\\work"),
  /POSIX syntax/u,
);
assert.throws(
  () => normalizeInstallerPath("C:\\Users\\alice\\ImgGen2", "darwin", "/tmp"),
  /belongs to Windows/u,
);
assert.equal(
  normalizeInstallerPath("/mnt/c/Users/alice/ImgGen2", "win32", "C:\\work"),
  "C:\\Users\\alice\\ImgGen2",
);
assert.equal(
  normalizeInstallerPath("file:///C:/Users/Alice/My%20Skills/ImgGen2", "win32", "C:\\work"),
  "C:\\Users\\Alice\\My Skills\\ImgGen2",
);
assert.equal(
  normalizeInstallerPath("file://server/share/ImgGen2", "win32", "C:\\work"),
  "\\\\server\\share\\ImgGen2",
);
const longPath = `C:\\work\\${"nested\\".repeat(40)}ImgGen2`;
assert.match(normalizeInstallerPath(longPath, "win32", "C:\\work"), /^\\\\\?\\C:\\/u);

console.log("Windows and cross-OS installer paths: OK");
