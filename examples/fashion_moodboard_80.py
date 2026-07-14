#!/usr/bin/env python3
"""80-cut fashion moodboard exploring one collection direction."""
from preset_runner import run_preset

if __name__ == "__main__":
    raise SystemExit(run_preset(
        slug="fashion-moodboard-80",
        prompt="도시의 새벽 통근복과 해체된 테일러링이 만나는 가상 패션 컬렉션 무드보드",
        style="Korean independent fashion editorial, restrained silhouette study, tactile textiles, no logos or readable text",
        count=80,
    ))
