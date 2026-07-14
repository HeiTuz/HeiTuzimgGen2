#!/usr/bin/env python3
"""24 lifestyle in-context scene directions for a usage-cut section."""
from preset_runner import run_preset

if __name__ == "__main__":
    raise SystemExit(run_preset(
        slug="lifestyle-product-scenes-24",
        prompt="가상의 원목 노트북 거치대를 실제 재택근무 책상 위에서 쓰는 라이프스타일 연출 컷",
        style="lifestyle product photography, believable Korean home-office context, natural window light, product remains the clear subject, fictional product, no readable text or logos",
        count=24,
    ))
