"""Parser for Codex CLI rollout JSONL session logs.

Recognizes the rollout envelope Codex writes per session
(``~/.codex/sessions/.../rollout-*.jsonl``): ``function_call`` /
``function_call_output`` response items and ``token_count`` events. Payloads
may appear wrapped (``{"type": ..., "payload": {...}}``) or bare; unrecognized
lines are skipped.
"""

import json

from oh_my_field.adapters.session_log.events import (
    ParsedSessionEvents,
    as_dict,
    as_int,
    as_list,
    as_str,
    as_text,
    iter_jsonl_objects,
    truncate,
)
from oh_my_field.domain.models import ToolCallRecord

PARSER_NAME = "codex"
_SHELL_TOOL_NAMES = frozenset(
    {"shell", "local_shell", "exec_command", "container.exec"}
)


def parse_codex_session(text: str) -> ParsedSessionEvents:
    payloads = tuple(_payload(entry) for entry in iter_jsonl_objects(text))
    outputs_by_call = _call_outputs(payloads)
    tool_calls: list[ToolCallRecord] = []
    commands: list[str] = []
    outputs: list[str] = []
    errors: list[str] = []
    input_tokens = 0
    output_tokens = 0
    for payload in payloads:
        payload_type = as_str(payload.get("type"))
        if payload_type in ("function_call", "custom_tool_call"):
            _collect_function_call(payload, outputs_by_call, tool_calls)
            _collect_command(payload, outputs_by_call, commands, outputs)
        elif payload_type == "local_shell_call":
            _collect_local_shell(payload, commands)
        elif payload_type == "error":
            _collect_error(payload, errors)
        elif payload_type == "token_count":
            # token_count events carry cumulative session totals; the last
            # event wins instead of summing.
            counted_input, counted_output = _token_counts(payload)
            if counted_input or counted_output:
                input_tokens, output_tokens = counted_input, counted_output
    return ParsedSessionEvents(
        parser=PARSER_NAME,
        tool_calls=tuple(tool_calls),
        commands=tuple(commands),
        outputs=tuple(outputs),
        errors=tuple(errors),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )


def _payload(entry: dict[str, object]) -> dict[str, object]:
    return as_dict(entry.get("payload")) or entry


def _collect_function_call(
    payload: dict[str, object],
    outputs_by_call: dict[str, str],
    tool_calls: list[ToolCallRecord],
) -> None:
    name = as_str(payload.get("name"))
    if name is None:
        return
    arguments = as_str(payload.get("arguments")) or as_text(payload.get("arguments"))
    call_id = as_str(payload.get("call_id")) or ""
    tool_calls.append(
        ToolCallRecord(
            tool=name,
            input=truncate(arguments),
            output=outputs_by_call.get(call_id, ""),
        ),
    )


def _collect_command(
    payload: dict[str, object],
    outputs_by_call: dict[str, str],
    commands: list[str],
    outputs: list[str],
) -> None:
    name = as_str(payload.get("name"))
    if name is None:
        return
    arguments = as_str(payload.get("arguments")) or as_text(payload.get("arguments"))
    command = _shell_command(name, arguments)
    if command is None:
        return
    commands.append(truncate(command))
    call_id = as_str(payload.get("call_id")) or ""
    output = outputs_by_call.get(call_id, "")
    if output:
        outputs.append(output)


def _collect_local_shell(payload: dict[str, object], commands: list[str]) -> None:
    action = as_dict(payload.get("action"))
    command = _command_text(action.get("command")) if action else None
    if command is not None:
        commands.append(truncate(command))


def _collect_error(payload: dict[str, object], errors: list[str]) -> None:
    message = as_str(payload.get("message"))
    if message is not None:
        errors.append(truncate(message))


def _call_outputs(payloads: tuple[dict[str, object], ...]) -> dict[str, str]:
    outputs: dict[str, str] = {}
    for payload in payloads:
        payload_type = as_str(payload.get("type"))
        if payload_type not in ("function_call_output", "custom_tool_call_output"):
            continue
        call_id = as_str(payload.get("call_id"))
        if call_id is None:
            continue
        outputs[call_id] = _output_text(payload.get("output"))
    return outputs


def _output_text(output: object) -> str:
    text = as_str(output)
    if text is None:
        return as_text(output)
    nested = _parsed_output_field(text)
    return truncate(nested if nested is not None else text)


def _parsed_output_field(text: str) -> str | None:
    # function_call_output payloads often wrap the real output in a JSON
    # object such as {"output": "...", "metadata": {...}}.
    if not text.startswith("{"):
        return None
    try:
        parsed: object = json.loads(text)
    except json.JSONDecodeError:
        return None
    parsed_dict = as_dict(parsed)
    if parsed_dict is None:
        return None
    return as_str(parsed_dict.get("output"))


def _shell_command(name: str, arguments: str) -> str | None:
    if name not in _SHELL_TOOL_NAMES:
        return None
    try:
        parsed: object = json.loads(arguments)
    except json.JSONDecodeError:
        return None
    parsed_dict = as_dict(parsed)
    if parsed_dict is None:
        return None
    return _command_text(parsed_dict.get("command"))


def _command_text(command: object) -> str | None:
    text = as_str(command)
    if text is not None:
        return text
    items = as_list(command)
    if items is None:
        return None
    parts = [part for part in (as_str(item) for item in items) if part is not None]
    return " ".join(parts) if parts else None


def _token_counts(payload: dict[str, object]) -> tuple[int, int]:
    info = as_dict(payload.get("info")) or payload
    usage = as_dict(info.get("total_token_usage")) or as_dict(
        info.get("last_token_usage"),
    )
    source = usage if usage is not None else info
    return (
        as_int(source.get("input_tokens")) or 0,
        as_int(source.get("output_tokens")) or 0,
    )
