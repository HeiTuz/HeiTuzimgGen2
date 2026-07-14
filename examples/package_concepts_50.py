#!/usr/bin/env python3
"""50 text-free packaging concept directions for an imaginary product."""
from preset_runner import run_preset

if __name__ == "__main__":
    raise SystemExit(run_preset(
        slug="package-concepts-50",
        prompt="가상의 소규모 로스터리가 판매하는 실험적인 콜드브루 병 패키지 콘셉트",
        style="independent packaging concept, shelf-readable silhouette and material system, fictional brand, no readable copy or logo",
        count=50,
    ))
