#!/usr/bin/env python3
"""Quietly remove expired HeiTuzImgGen2 temporary job directories."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Sequence

from output_lifecycle import cleanup_expired, retention_hours, temp_root


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--retention-hours", type=float)
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--now", type=float, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        root = temp_root()
        hours = args.retention_hours if args.retention_hours is not None else retention_hours()
        removed = cleanup_expired(
            retention_hours=hours,
            now=args.now,
        )
    except (OSError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    if args.verbose:
        print(
            json.dumps(
                {
                    "root": str(root),
                    "retention_hours": hours,
                    "removed_count": len(removed),
                    "removed": [str(path) for path in removed],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
