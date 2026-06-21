#!/usr/bin/env python3
import sys
from pathlib import Path

EXPECTED_ARTIFACTS = ['opus_run.log', 'validation.txt', 'output/normalized.json']


def main() -> int:
    missing = [path for path in EXPECTED_ARTIFACTS if not Path(path).exists()]
    if missing:
        for path in missing:
            print(f"missing artifact: {path}", file=sys.stderr)
        return 1
    print("contract validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
