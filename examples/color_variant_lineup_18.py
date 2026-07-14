#!/usr/bin/env python3
"""18 color-variant lineup directions for option-selector imagery."""
from preset_runner import run_preset

if __name__ == "__main__":
    raise SystemExit(run_preset(
        slug="color-variant-lineup-18",
        prompt="가상의 실리콘 폰케이스 컬러 옵션을 한눈에 비교할 수 있는 변형 라인업 컷",
        style="color variant lineup, consistent camera angle and lighting across variants, evenly spaced arrangement, accurate hue separation, fictional product, no readable text",
        count=18,
    ))
