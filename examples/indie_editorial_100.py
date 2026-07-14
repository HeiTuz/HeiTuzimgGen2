#!/usr/bin/env python3
"""100-cut subculture and indie editorial reference board."""
from preset_runner import run_preset

if __name__ == "__main__":
    raise SystemExit(run_preset(
        slug="indie-editorial-100",
        prompt="독립 잡지 화보처럼 낯설고 건조한 검은 고양이 초상",
        style="anti-mainstream Korean indie editorial, DIY zine energy, dry humor, no readable text",
        count=100,
    ))
