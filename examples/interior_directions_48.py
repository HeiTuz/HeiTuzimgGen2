#!/usr/bin/env python3
"""48 visual directions for a small cultural interior."""
from preset_runner import run_preset

if __name__ == "__main__":
    raise SystemExit(run_preset(
        slug="interior-directions-48",
        prompt="오래된 세탁소를 개조한 12평 규모의 독립 서점 겸 심야 청음 공간",
        style="spatial concept photography, buildable material logic, Korean urban context, atmospheric but operationally plausible",
        count=48,
    ))
