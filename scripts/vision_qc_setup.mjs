#!/usr/bin/env node

const status = process.argv.includes("--status");

if (status) {
  console.log(JSON.stringify({ vision_qc: "auto", reviewer: "host-default-vision" }));
  process.exit(0);
}

console.log(`Vision-QC setup

ImgGen2 uses the host's default Vision model in auto mode.

Hermes configuration:
  auxiliary.vision.provider: auto
  auxiliary.vision.model: ""

Inspect or change the active host model with:
  hermes config
  hermes config set auxiliary.vision.provider auto
  hermes config set auxiliary.vision.model ""

No separate QC API key or pinned reviewer model is required.`);
