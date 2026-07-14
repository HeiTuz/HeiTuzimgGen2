#!/usr/bin/env python3
"""Reusable example: compile and generate varied reference-board images."""
from pathlib import Path
import runpy
import sys

if __name__ == "__main__":
    scripts = Path(__file__).resolve().parent.parent / "scripts"
    sys.path.insert(0, str(scripts))
    runpy.run_path(str(scripts / "creative_batch.py"), run_name="__main__")
