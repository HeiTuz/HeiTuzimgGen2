#!/usr/bin/env node
import { spawnSync } from "node:child_process";

const candidates = process.platform === "win32"
  ? [["python", []], ["py", ["-3"]], ["python3", []]]
  : [["python3", []], ["python", []]];

let selected = null;
for (const [command, prefix] of candidates) {
  const probe = spawnSync(command, [...prefix, "--version"], {
    encoding: "utf8",
  });
  if (!probe.error && probe.status === 0) {
    selected = [command, prefix];
    break;
  }
}

if (selected === null) {
  console.error("HeiTuzImgGen2 tests: Python 3 was not found on PATH.");
  process.exitCode = 1;
} else {
  const [command, prefix] = selected;
  const commands = [
    ["-m", "unittest", "discover", "-s", "scripts", "-p", "test_*.py", "-v"],
    ["-m", "compileall", "-q", "scripts"],
  ];
  for (const args of commands) {
    const result = spawnSync(command, [...prefix, ...args], { stdio: "inherit" });
    if (result.error || result.status !== 0) {
      console.error(
        `HeiTuzImgGen2 tests: ${command} ${[...prefix, ...args].join(" ")} failed` +
        (result.error ? `: ${result.error.message}` : ` (exit ${result.status})`),
      );
      process.exitCode = result.status || 1;
      break;
    }
  }
}
