#!/usr/bin/env python3
"""Contract validator for the csv_normalize capability.

Run from the target artifact root (the directory that holds ``output/``). OMF's
``omf capability validate --run-contract-validator`` invokes this with that
directory as the working directory and trusts the exit code, so this enforces the
contract for real rather than rubber-stamping file existence:

- ``output/normalized.json`` exists,
- it is valid JSON, and
- it matches the record schema/types the capability promises.

Value-level correctness against the golden output is intentionally *not* checked
here -- that is ``examples/10min-happy-path/check.py``'s job. This validator
proves the *shape* is contract-valid; ``check.py`` proves the *values* are right.

Exit code 0 = contract satisfied, 1 = any violation (printed to stderr).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ARTIFACT = Path("output/normalized.json")
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
RECORD_KEYS = {
    "order_id",
    "customer",
    "email",
    "amount_usd",
    "ordered_on",
    "fulfilled",
}


def _is_number(value: object) -> bool:
    # bool is a subclass of int; `0`/`1` must NOT satisfy a numeric field.
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _extract_json(text: str) -> str:
    """Pull the JSON payload out of the artifact text.

    The contract says write pure JSON, but tolerate an accidental ```json fence
    or prose preamble so this validator agrees with ``check.py``'s parsing.
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


def _check_record(record: object, index: int) -> list[str]:
    trail = f"records[{index}]"
    if not isinstance(record, dict):
        return [f"{trail}: expected object, got {type(record).__name__}"]
    errors: list[str] = []
    keys = set(record.keys())
    missing = RECORD_KEYS - keys
    extra = keys - RECORD_KEYS
    if missing:
        errors.append(f"{trail}: missing key(s) {sorted(missing)}")
    if extra:
        errors.append(f"{trail}: unexpected key(s) {sorted(extra)}")

    def _require(key: str, ok: bool, expected: str) -> None:  # noqa: FBT001
        if key in record and not ok:
            errors.append(
                f"{trail}.{key}: expected {expected}, got "
                f"{type(record[key]).__name__}",
            )

    _require("order_id", isinstance(record.get("order_id"), int)
             and not isinstance(record.get("order_id"), bool), "integer")
    _require("customer", isinstance(record.get("customer"), str), "string")
    _require("email", isinstance(record.get("email"), str), "string")
    _require("amount_usd", _is_number(record.get("amount_usd")), "number")
    _require("fulfilled", isinstance(record.get("fulfilled"), bool), "boolean")
    if "ordered_on" in record:
        value = record["ordered_on"]
        if not isinstance(value, str) or not ISO_DATE.match(value):
            errors.append(f"{trail}.ordered_on: expected YYYY-MM-DD string, got {value!r}")
    return errors


def _validate(payload: object) -> list[str]:
    if not isinstance(payload, dict):
        return [f"<root>: expected object, got {type(payload).__name__}"]
    if set(payload.keys()) != {"records"}:
        return [f"<root>: expected exactly key 'records', got {sorted(payload.keys())}"]
    records = payload["records"]
    if not isinstance(records, list):
        return [f"records: expected list, got {type(records).__name__}"]
    errors: list[str] = []
    for index, record in enumerate(records):
        errors.extend(_check_record(record, index))
    return errors


def main() -> int:
    if not ARTIFACT.exists():
        print(f"missing artifact: {ARTIFACT}", file=sys.stderr)
        return 1
    try:
        payload = json.loads(_extract_json(ARTIFACT.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"invalid JSON in {ARTIFACT}: {exc}", file=sys.stderr)
        return 1
    errors = _validate(payload)
    if errors:
        for error in errors:
            print(f"schema violation: {error}", file=sys.stderr)
        return 1
    print("contract validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
