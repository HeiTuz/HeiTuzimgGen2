#!/usr/bin/env python3
"""24 beauty and cosmetics product visual directions."""
from preset_runner import run_preset

if __name__ == "__main__":
    raise SystemExit(run_preset(
        slug="beauty-cosmetics-shots-24",
        prompt="가상의 비건 세럼 라인을 텍스처 스와치·물방울·유리 소재와 함께 연출한 뷰티 제품컷",
        style="K-beauty commerce photography, dewy texture swatches, glass and water elements, soft gradient backdrop, fictional brand, no readable label copy",
        count=24,
    ))
