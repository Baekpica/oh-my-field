#!/usr/bin/env python3
"""Objective pass/fail for the 10-minute happy path.

Compares a produced JSON file against the committed golden
``expected/normalized.json`` using a *semantic* deep-equal: both sides are parsed
to Python objects before comparing, so whitespace, key order, and 2000 vs 2000.0
do not matter -- only the values do.

Usage:
    python check.py <produced.json>

Exit code 0 = PASS (matches golden), 1 = FAIL (mismatch / unreadable).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOLDEN = HERE / "expected" / "normalized.json"


def _extract_json(text: str) -> str:
    """Pull the JSON payload out of model output.

    Models sometimes wrap output in ```json ... ``` or add a prose preamble.
    That is a transport artifact, not a data error, so we extract the JSON
    before parsing. The extraction is applied identically to every condition,
    so it never advantages one model: wrong *structure* still fails the check.
    """
    text = text.strip()
    fence = re.search(r"```(?:json|JSON)?\s*\n(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    starts = [i for i in (text.find("{"), text.find("[")) if i != -1]
    if starts:
        start = min(starts)
        end = max(text.rfind("}"), text.rfind("]"))
        if end > start:
            text = text[start : end + 1]
    return text


def _load(path: Path) -> object:
    text = path.read_text(encoding="utf-8")
    return json.loads(_extract_json(text))


def _first_diff(produced: object, golden: object, trail: str = "") -> str | None:
    """Return a short human-readable description of the first mismatch."""
    both_numbers = isinstance(produced, (int, float)) and isinstance(
        golden, (int, float)
    )
    if type(produced) is not type(golden) and not both_numbers:
        p_type, g_type = type(produced).__name__, type(golden).__name__
        return f"{trail or '<root>'}: type {p_type} != {g_type}"
    if isinstance(golden, dict) and isinstance(produced, dict):
        for key in golden:
            if key not in produced:
                return f"{trail}.{key}: missing in produced output"
            sub = _first_diff(produced[key], golden[key], f"{trail}.{key}")
            if sub:
                return sub
        extra = set(produced) - set(golden)
        if extra:
            return f"{trail or '<root>'}: unexpected key(s) {sorted(extra)}"
        return None
    if isinstance(golden, list) and isinstance(produced, list):
        if len(produced) != len(golden):
            return f"{trail or '<root>'}: list length {len(produced)} != {len(golden)}"
        for i, (p, g) in enumerate(zip(produced, golden, strict=False)):
            sub = _first_diff(p, g, f"{trail}[{i}]")
            if sub:
                return sub
        return None
    if produced != golden:
        return f"{trail or '<root>'}: {produced!r} != {golden!r}"
    return None


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: python check.py <produced.json>", file=sys.stderr)
        return 1
    produced_path = Path(argv[1])
    try:
        golden = _load(GOLDEN)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"FAIL: cannot read golden {GOLDEN}: {exc}", file=sys.stderr)
        return 1
    try:
        produced = _load(produced_path)
    except FileNotFoundError:
        print(f"FAIL: produced file not found: {produced_path}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as exc:
        print(f"FAIL: produced file is not valid JSON: {exc}", file=sys.stderr)
        return 1

    diff = _first_diff(produced, golden)
    if diff is None:
        print("PASS: output matches the golden normalized.json")
        return 0
    print(f"FAIL: {diff}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
