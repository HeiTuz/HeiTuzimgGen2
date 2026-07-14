#!/usr/bin/env python3
"""24 home and living staging directions for interior commerce cuts."""
from preset_runner import run_preset

if __name__ == "__main__":
    raise SystemExit(run_preset(
        slug="home-living-scenes-24",
        prompt="가상의 리넨 침구 세트를 다양한 시간대의 침실 무드로 연출한 홈리빙 판매 컷",
        style="home and living commerce photography, realistic Korean apartment staging, layered textiles, warm believable light, fictional product, no readable text or logos",
        count=24,
    ))
