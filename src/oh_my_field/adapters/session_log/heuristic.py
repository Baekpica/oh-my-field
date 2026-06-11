"""Best-effort parser for unknown JSONL session log formats.

Used for runtimes without a dedicated parser (hermes, pi, odysseus) and as
the fallback when a dedicated parser recognizes nothing. Looks for common
event shapes — tool/name + input/arguments, command strings, error strings,
usage token counts — and skips everything else.
"""

from oh_my_field.adapters.session_log.events import (
    ParsedSessionEvents,
    as_dict,
    as_int,
    as_str,
    as_text,
    iter_jsonl_objects,
    truncate,
)
from oh_my_field.domain.models import ToolCallRecord

PARSER_NAME = "heuristic_jsonl"
_TOOL_EVENT_TYPES = frozenset({"tool_use", "tool_call", "function_call"})


def parse_heuristic_session(text: str) -> ParsedSessionEvents:
    tool_calls: list[ToolCallRecord] = []
    commands: list[str] = []
    errors: list[str] = []
    input_tokens = 0
    output_tokens = 0
    for entry in iter_jsonl_objects(text):
        tool = _tool_name(entry)
        if tool is not None:
            tool_calls.append(
                ToolCallRecord(
                    tool=tool,
                    input=as_text(_tool_input(entry)),
                    output=truncate(as_str(entry.get("output")) or ""),
                ),
            )
        command = as_str(entry.get("command"))
        if command is not None:
            commands.append(truncate(command))
        error = as_str(entry.get("error"))
        if error is not None:
            errors.append(truncate(error))
        usage = as_dict(entry.get("usage"))
        if usage is not None:
            input_tokens += as_int(usage.get("input_tokens")) or 0
            output_tokens += as_int(usage.get("output_tokens")) or 0
    return ParsedSessionEvents(
        parser=PARSER_NAME,
        tool_calls=tuple(tool_calls),
        commands=tuple(commands),
        errors=tuple(errors),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )


def _tool_name(entry: dict[str, object]) -> str | None:
    tool = as_str(entry.get("tool"))
    if tool is not None:
        return tool
    if as_str(entry.get("type")) in _TOOL_EVENT_TYPES:
        return as_str(entry.get("name"))
    return None


def _tool_input(entry: dict[str, object]) -> object:
    for key in ("input", "arguments", "args"):
        if key in entry:
            return entry[key]
    return ""
