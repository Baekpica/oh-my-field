"""Parser for Claude Code JSONL session logs.

Recognizes the message envelope Claude Code writes per session
(``~/.claude/projects/<project>/<session>.jsonl``): assistant messages carry
``tool_use`` content blocks and token usage, user messages carry the matching
``tool_result`` blocks. Unrecognized lines are skipped.
"""

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

PARSER_NAME = "claude_code"


def parse_claude_code_session(text: str) -> ParsedSessionEvents:
    objects = tuple(iter_jsonl_objects(text))
    results, error_ids = _tool_results(objects)
    tool_calls: list[ToolCallRecord] = []
    commands: list[str] = []
    outputs: list[str] = []
    errors: list[str] = []
    input_tokens = 0
    output_tokens = 0
    for entry in objects:
        message = as_dict(entry.get("message"))
        if message is None or as_str(message.get("role")) != "assistant":
            continue
        usage = as_dict(message.get("usage"))
        if usage is not None:
            input_tokens += as_int(usage.get("input_tokens")) or 0
            output_tokens += as_int(usage.get("output_tokens")) or 0
        for block in as_list(message.get("content")) or []:
            block_dict = as_dict(block)
            if block_dict is None or as_str(block_dict.get("type")) != "tool_use":
                continue
            tool = as_str(block_dict.get("name"))
            if tool is None:
                continue
            block_id = as_str(block_dict.get("id")) or ""
            output = results.get(block_id, "")
            tool_calls.append(
                ToolCallRecord(
                    tool=tool,
                    input=as_text(block_dict.get("input")),
                    output=output,
                ),
            )
            if block_id in error_ids and output:
                errors.append(output)
            tool_input = as_dict(block_dict.get("input"))
            command = as_str(tool_input.get("command")) if tool_input else None
            if tool.casefold() == "bash" and command is not None:
                commands.append(truncate(command))
                if output and block_id not in error_ids:
                    outputs.append(output)
    return ParsedSessionEvents(
        parser=PARSER_NAME,
        tool_calls=tuple(tool_calls),
        commands=tuple(commands),
        outputs=tuple(outputs),
        errors=tuple(errors),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )


def _tool_results(
    objects: tuple[dict[str, object], ...],
) -> tuple[dict[str, str], set[str]]:
    results: dict[str, str] = {}
    error_ids: set[str] = set()
    for entry in objects:
        message = as_dict(entry.get("message"))
        if message is None:
            continue
        for block in as_list(message.get("content")) or []:
            block_dict = as_dict(block)
            if block_dict is None or as_str(block_dict.get("type")) != "tool_result":
                continue
            tool_use_id = as_str(block_dict.get("tool_use_id"))
            if tool_use_id is None:
                continue
            results[tool_use_id] = _result_text(block_dict.get("content"))
            if block_dict.get("is_error") is True:
                error_ids.add(tool_use_id)
    return results, error_ids


def _result_text(content: object) -> str:
    text = as_str(content)
    if text is not None:
        return truncate(text)
    parts: list[str] = []
    for item in as_list(content) or []:
        item_dict = as_dict(item)
        if item_dict is None:
            continue
        part = as_str(item_dict.get("text"))
        if part is not None:
            parts.append(part)
    return truncate("\n".join(parts))
