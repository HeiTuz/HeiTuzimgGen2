#!/usr/bin/env python3
"""40 distinct cover-art directions for a fictional music release."""
from preset_runner import run_preset

if __name__ == "__main__":
    raise SystemExit(run_preset(
        slug="album-cover-directions-40",
        prompt="새벽 첫차가 끊긴 뒤의 서울을 주제로 한 가상 인디 전자음악 앨범 커버",
        style="conceptual record sleeve, emotionally cold but human, graphic focal image, no artist name or readable typography",
        count=40,
    ))
