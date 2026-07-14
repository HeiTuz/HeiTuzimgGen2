#!/usr/bin/env python3
"""20 material and craftsmanship close-up directions for detail pages."""
from preset_runner import run_preset

if __name__ == "__main__":
    raise SystemExit(run_preset(
        slug="detail-closeups-20",
        prompt="가상의 가죽 카드지갑에서 스티치·엣지·결 같은 소재 디테일을 강조한 클로즈업 컷",
        style="macro product detail photography, tactile material texture, shallow depth of field, raking light to reveal stitching and grain, fictional product, no readable text",
        count=20,
    ))
