import json

from oh_my_field.adapters.session_log import (
    parse_claude_code_session,
    parse_codex_session,
    parse_session_log,
)

CLAUDE_CODE_LOG = "\n".join(
    [
        json.dumps(
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "toolu_1",
                            "name": "Bash",
                            "input": {"command": "pytest -q"},
                        },
                    ],
                    "usage": {"input_tokens": 120, "output_tokens": 45},
                },
            },
        ),
        json.dumps(
            {
                "type": "user",
                "message": {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "toolu_1",
                            "content": "2 passed",
                        },
                    ],
                },
            },
        ),
        json.dumps(
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "done"}],
                    "usage": {"input_tokens": 30, "output_tokens": 10},
                },
            },
        ),
        "not json at all",
    ],
)

CODEX_LOG = "\n".join(
    [
        json.dumps(
            {
                "type": "response_item",
                "payload": {
                    "type": "function_call",
                    "name": "shell",
                    "arguments": json.dumps({"command": ["pytest", "-q"]}),
                    "call_id": "call_1",
                },
            },
        ),
        json.dumps(
            {
                "type": "response_item",
                "payload": {
                    "type": "function_call_output",
                    "call_id": "call_1",
                    "output": json.dumps(
                        {"output": "2 passed", "metadata": {"exit_code": 0}},
                    ),
                },
            },
        ),
        json.dumps(
            {
                "type": "event_msg",
                "payload": {
                    "type": "token_count",
                    "info": {
                        "total_token_usage": {
                            "input_tokens": 200,
                            "output_tokens": 80,
                        },
                    },
                },
            },
        ),
    ],
)


def test_claude_code_parser_extracts_tool_calls_commands_and_usage() -> None:
    events = parse_claude_code_session(CLAUDE_CODE_LOG)

    assert events.parser == "claude_code"
    assert [call.tool for call in events.tool_calls] == ["Bash"]
    assert events.tool_calls[0].output == "2 passed"
    assert events.commands == ("pytest -q",)
    assert events.outputs == ("2 passed",)
    assert events.errors == ()
    assert events.input_tokens == 150
    assert events.output_tokens == 55


def test_claude_code_parser_records_tool_result_errors() -> None:
    log = "\n".join(
        [
            json.dumps(
                {
                    "message": {
                        "role": "assistant",
                        "content": [
                            {
                                "type": "tool_use",
                                "id": "toolu_9",
                                "name": "Bash",
                                "input": {"command": "pytest -q"},
                            },
                        ],
                    },
                },
            ),
            json.dumps(
                {
                    "message": {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": "toolu_9",
                                "content": "1 failed",
                                "is_error": True,
                            },
                        ],
                    },
                },
            ),
        ],
    )

    events = parse_claude_code_session(log)

    assert events.errors == ("1 failed",)
    assert events.outputs == ()


def test_codex_parser_extracts_shell_commands_and_cumulative_usage() -> None:
    events = parse_codex_session(CODEX_LOG)

    assert events.parser == "codex"
    assert [call.tool for call in events.tool_calls] == ["shell"]
    assert events.commands == ("pytest -q",)
    assert events.outputs == ("2 passed",)
    assert events.input_tokens == 200
    assert events.output_tokens == 80


def test_dedicated_parser_falls_back_to_heuristic_for_unknown_shapes() -> None:
    log = "\n".join(
        [
            json.dumps({"tool": "search", "input": {"query": "docs"}}),
            json.dumps({"command": "make test"}),
            json.dumps({"error": "flaky network"}),
            json.dumps({"usage": {"input_tokens": 10, "output_tokens": 5}}),
        ],
    )

    events = parse_session_log("claude_code", log)

    assert events.parser == "heuristic_jsonl"
    assert [call.tool for call in events.tool_calls] == ["search"]
    assert events.commands == ("make test",)
    assert events.errors == ("flaky network",)
    assert events.input_tokens == 10
    assert events.output_tokens == 5


def test_plain_text_log_parses_to_empty_events() -> None:
    events = parse_session_log("hermes", "Hermes completed a long run.\nall good\n")

    assert not events.has_content()
