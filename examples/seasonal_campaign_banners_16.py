#!/usr/bin/env python3
"""16 seasonal campaign banner background directions with copy space."""
from preset_runner import run_preset

if __name__ == "__main__":
    raise SystemExit(run_preset(
        slug="seasonal-campaign-banners-16",
        prompt="여름 시즌 프로모션에 쓸 가상의 선케어 라인 배너 비주얼, 카피를 얹을 여백 확보",
        style="wide campaign banner composition, seasonal summer palette, generous negative space reserved for overlay copy, fictional brand, no readable text baked into the image",
        count=16,
    ))
