#!/usr/bin/env python3
"""32 marketplace thumbnail directions that survive small-grid browsing."""
from preset_runner import run_preset

if __name__ == "__main__":
    raise SystemExit(run_preset(
        slug="marketplace-thumbnails-32",
        prompt="오픈마켓 검색 결과에서 눈에 띄는 가상의 스테인리스 텀블러 썸네일 컷",
        style="marketplace thumbnail composition, single dominant product, high contrast against simple background, legible at 200px grid size, fictional product, no readable text",
        count=32,
    ))
