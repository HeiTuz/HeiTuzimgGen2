#!/usr/bin/env python3
"""24 food and beverage appetite-appeal directions for commerce pages."""
from preset_runner import run_preset

if __name__ == "__main__":
    raise SystemExit(run_preset(
        slug="food-beverage-shots-24",
        prompt="가상의 수제 그래놀라와 병 음료를 아침 식탁 맥락으로 연출한 식품 판매용 컷",
        style="appetizing food commerce photography, fresh ingredient styling, natural morning light, honest portion presentation, fictional brand, no readable packaging text",
        count=24,
    ))
