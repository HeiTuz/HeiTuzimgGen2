#!/usr/bin/env python3
"""64 silhouette-first directions for one fictional character family."""
from preset_runner import run_preset

if __name__ == "__main__":
    raise SystemExit(run_preset(
        slug="character-silhouettes-64",
        prompt="낡은 지하상가에서 이상한 물건을 수집하는 가상 캐릭터의 전신 실루엣 탐색",
        style="silhouette-first character design sheet as standalone art, strong shape language, restrained details, no labels or UI",
        count=64,
    ))
