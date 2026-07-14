#!/usr/bin/env python3
"""24 clean product hero directions for a detail-page first cut."""
from preset_runner import run_preset

if __name__ == "__main__":
    raise SystemExit(run_preset(
        slug="product-hero-shots-24",
        prompt="가상의 무선 미니 가습기를 상세페이지 첫 컷으로 쓸 수 있는 깨끗한 히어로 제품컷",
        style="clean ecommerce hero shot, seamless studio background, controlled softbox lighting, true-to-form product silhouette, fictional product, no readable text or logos",
        count=24,
    ))
