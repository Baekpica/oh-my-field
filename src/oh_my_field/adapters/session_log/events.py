"""Runtime-neutral structured events parsed from an agent session log.

Parsing is enrichment, not a gate: parsers consume the captured (already
redacted) log text, recognize what they can, and skip everything else. A log
that yields no events is imported exactly as before.
"""

import json
from collections.abc import Iterator
from typing import Final, cast

from oh_my_field.domain.models import StrictModel, ToolCallRecord

MAX_FIELD_CHARS: Final = 2000
TRUNCATION_MARKER: Final = "...[truncated]"


class ParsedSessionEvents(StrictModel):
    parser: str
    tool_calls: tuple[ToolCallRecord, ...] = ()
    commands: tuple[str, ...] = ()
    outputs: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    input_tokens: int = 0
    output_tokens: int = 0

    def has_content(self) -> bool:
        return bool(
            self.tool_calls
            or self.commands
            or self.outputs
            or self.errors
            or self.input_tokens
            or self.output_tokens,
        )


def iter_jsonl_objects(text: str) -> Iterator[dict[str, object]]:
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line.startswith("{"):
            continue
        try:
            parsed: object = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            yield cast("dict[str, object]", parsed)


def as_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def as_dict(value: object) -> dict[str, object] | None:
    if isinstance(value, dict):
        return cast("dict[str, object]", value)
    return None


def as_list(value: object) -> list[object] | None:
    if isinstance(value, list):
        return cast("list[object]", value)
    return None


def as_int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def truncate(text: str) -> str:
    if len(text) <= MAX_FIELD_CHARS:
        return text
    return f"{text[:MAX_FIELD_CHARS]}{TRUNCATION_MARKER}"


def as_text(value: object) -> str:
    if isinstance(value, str):
        return truncate(value)
    return truncate(json.dumps(value, ensure_ascii=False, sort_keys=True))
