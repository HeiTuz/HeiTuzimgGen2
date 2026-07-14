#!/usr/bin/env python3
"""16 bundle and gift-set composition directions for set SKUs."""
from preset_runner import run_preset

if __name__ == "__main__":
    raise SystemExit(run_preset(
        slug="bundle-set-compositions-16",
        prompt="가상의 홈카페 스타터 세트를 드리퍼·서버·원두 구성으로 보여주는 번들 구성 컷",
        style="bundle set composition, clear item hierarchy, top-down and three-quarter arrangements, cohesive prop palette, fictional products, no readable text or logos",
        count=16,
    ))
