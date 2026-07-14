#!/usr/bin/env python3
"""28 apparel catalog look directions for a seasonal lookbook draft."""
from preset_runner import run_preset

if __name__ == "__main__":
    raise SystemExit(run_preset(
        slug="apparel-catalog-looks-28",
        prompt="가상의 여성복 가을 신상 라인을 카탈로그 룩 단위로 탐색하는 의류 판매용 컷",
        style="apparel catalog photography, full-body and half-body framing mix, neutral studio and street backdrops, consistent model direction, fictional brand, no logos or readable text",
        count=28,
    ))
