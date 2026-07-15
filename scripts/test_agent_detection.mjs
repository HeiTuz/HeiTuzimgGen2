#!/usr/bin/env node
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import {
  detectAgentHosts,
  deterministicAgentHosts,
  parseInteractiveAgentHosts,
} from "./agent_targets.mjs";
import { hostInstallPlan, installPayload, installPlansTransaction, parse } from "./install.mjs";

function fakeExists(homeDir, relativePaths) {
  const paths = new Set(relativePaths.map((relative) => path.join(homeDir, relative)));
  return (candidate) => paths.has(candidate);
}

const home = path.join(os.tmpdir(), "agent-detection-home");
assert.deepEqual(detectAgentHosts({ homeDir: home, existsSync: fakeExists(home, [".hermes"]) }), ["hermes"]);
assert.deepEqual(detectAgentHosts({ homeDir: home, existsSync: fakeExists(home, [".claude"]) }), ["claude"]);
assert.deepEqual(detectAgentHosts({ homeDir: home, existsSync: fakeExists(home, [".codex", ".codex/skills"]) }), ["codex"]);
assert.deepEqual(detectAgentHosts({ homeDir: home, existsSync: fakeExists(home, [".codex", ".claude", ".hermes"]) }), ["hermes", "claude", "codex"]);
assert.deepEqual(detectAgentHosts({ homeDir: home, existsSync: () => false }), []);
assert.deepEqual(detectAgentHosts({ homeDir: home, existsSync: () => false, cliSignals: { claude: true } }), ["claude"]);

assert.deepEqual(deterministicAgentHosts("auto", ["codex", "claude"]), ["claude"]);
assert.deepEqual(deterministicAgentHosts("auto", ["codex", "hermes"]), ["hermes"]);
assert.deepEqual(deterministicAgentHosts("auto", []), ["hermes"]);
assert.deepEqual(deterministicAgentHosts("all", ["codex", "claude"]), ["claude", "codex"]);
assert.deepEqual(parseInteractiveAgentHosts("hermes,codex", ["claude"]), ["hermes", "codex"]);
assert.equal(parse([]).agent, "auto");
assert.equal(parse(["--", "--agent", "gpt"]).agent, "gpt");
assert.deepEqual(hostInstallPlan(home, "claude"), {
  host: "claude",
  destination: path.resolve(home, ".claude", "skills", "HeiTuzImgGen2"),
  mpwTarget: path.resolve(home, ".claude", "skills", "HeiTuzMPW"),
});
const installer = fileURLToPath(new URL("./install.mjs", import.meta.url));
const unsafeHome = fs.mkdtempSync(path.join(os.tmpdir(), "imggen-unsafe-target-"));
try {
  const unsafe = spawnSync(process.execPath, [installer, "--target", unsafeHome, "--offline", "--force"], {
    encoding: "utf8",
    env: { ...process.env, HOME: unsafeHome, USERPROFILE: unsafeHome, XDG_CONFIG_HOME: path.join(unsafeHome, "config"), CI: "1" },
  });
  assert.notEqual(unsafe.status, 0);
  assert.match(unsafe.stderr, /unsafe install destination/u);
  const protectedContainer = spawnSync(process.execPath, [installer, "--target", path.join(unsafeHome, ".claude", "skills"), "--offline", "--force"], {
    encoding: "utf8",
    env: { ...process.env, HOME: unsafeHome, USERPROFILE: unsafeHome, XDG_CONFIG_HOME: path.join(unsafeHome, "config"), CI: "1" },
  });
  assert.notEqual(protectedContainer.status, 0);
  assert.match(protectedContainer.stderr, /unsafe install destination/u);
} finally {
  fs.rmSync(unsafeHome, { recursive: true, force: true });
}

const temp = fs.mkdtempSync(path.join(os.tmpdir(), "imggen-overlay-test-"));
try {
  const fixture = path.join(temp, "source");
  const destination = path.join(temp, "installed");
  fs.mkdirSync(path.join(fixture, "agents", "codex"), { recursive: true });
  fs.mkdirSync(path.join(fixture, "references"), { recursive: true });
  fs.writeFileSync(path.join(fixture, "SKILL.md"), "canonical\n");
  fs.writeFileSync(path.join(fixture, "README.md"), "shared\n");
  fs.writeFileSync(path.join(fixture, "references", ".private"), "excluded\n");
  fs.writeFileSync(path.join(fixture, "agents", "codex", "SKILL.md"), "codex-adapted\n");
  installPayload({ sourceRoot: fixture, destination, host: "codex" });
  assert.equal(fs.readFileSync(path.join(destination, "SKILL.md"), "utf8"), "codex-adapted\n");
  assert.equal(fs.existsSync(path.join(destination, "agents")), false);
  assert.equal(fs.existsSync(path.join(destination, "references", ".private")), false);
  const transactionalDestination = path.join(temp, "transactional");
  fs.mkdirSync(transactionalDestination, { recursive: true });
  fs.writeFileSync(path.join(transactionalDestination, "stale.txt"), "old\n");
  installPlansTransaction(
    [{ destination: transactionalDestination, mpwTarget: path.join(temp, "mpw"), host: "codex" }],
    { requested: "auto", effective: "auto" },
    { sourceRoot: fixture },
  );
  assert.equal(fs.existsSync(path.join(transactionalDestination, "stale.txt")), false);
  assert.equal(fs.readFileSync(path.join(transactionalDestination, "SKILL.md"), "utf8"), "codex-adapted\n");

  const failingSource = path.join(temp, "failing-source");
  const preservedDestination = path.join(temp, "preserved");
  fs.mkdirSync(failingSource, { recursive: true });
  fs.mkdirSync(preservedDestination, { recursive: true });
  fs.writeFileSync(path.join(failingSource, "SKILL.md"), "canonical\n");
  fs.writeFileSync(path.join(preservedDestination, "marker.txt"), "preserved\n");
  assert.throws(
    () => installPlansTransaction(
      [{ destination: preservedDestination, mpwTarget: path.join(temp, "mpw-failing"), host: "codex" }],
      { requested: "auto", effective: "auto" },
      { sourceRoot: failingSource },
    ),
    /missing the codex agent overlay/u,
  );
  assert.equal(fs.readFileSync(path.join(preservedDestination, "marker.txt"), "utf8"), "preserved\n");
  assert.equal(fs.readdirSync(temp).some((entry) => entry.startsWith(".heituzimggen2-stage-")), false);
} finally {
  fs.rmSync(temp, { recursive: true, force: true });
}

console.log("agent detection, target alignment, and overlay selection: OK");
