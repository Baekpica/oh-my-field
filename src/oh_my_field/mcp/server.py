import json
import sys
from collections.abc import Mapping
from typing import cast

from oh_my_field.mcp.tools import dispatch_tool, mcp_tool_definitions

type JsonValue = (
    str | int | float | bool | None | list["JsonValue"] | dict[str, "JsonValue"]
)
type JsonObject = dict[str, JsonValue]


def serve_stdio() -> None:
    for line in sys.stdin:
        response = handle_line(line)
        if response is None:
            continue
        sys.stdout.write(f"{response}\n")
        sys.stdout.flush()


def handle_line(line: str) -> str | None:
    try:
        parsed = cast("object", json.loads(line))
    except json.JSONDecodeError as exc:
        return json.dumps(_error(None, -32700, f"parse error: {exc}"))
    if not isinstance(parsed, Mapping):
        return json.dumps(_error(None, -32600, "request must be a JSON object"))
    response = handle_message(cast("Mapping[str, object]", parsed))
    if response is None:
        return None
    return json.dumps(response)


def handle_message(message: Mapping[str, object]) -> JsonObject | None:  # noqa: PLR0911
    request_id = _json_id(message.get("id"))
    method = message.get("method")
    if not isinstance(method, str):
        return _error(request_id, -32600, "request method must be a string")
    if "id" not in message and method.startswith("notifications/"):
        return None
    if method == "initialize":
        return _result(request_id, _initialize_result())
    if method == "ping":
        return _result(request_id, {})
    if method == "tools/list":
        return _result(
            request_id,
            {"tools": list(mcp_tool_definitions())},
        )
    if method == "tools/call":
        return _call_tool(request_id, message.get("params"))
    return _error(request_id, -32601, f"unknown method {method!r}")


def _call_tool(request_id: JsonValue, params: object) -> JsonObject:
    if not isinstance(params, Mapping):
        return _error(request_id, -32602, "tools/call params must be an object")
    params_map = cast("Mapping[str, object]", params)
    name = params_map.get("name")
    if not isinstance(name, str):
        return _error(request_id, -32602, "tools/call params.name must be a string")
    arguments = params_map.get("arguments", {})
    if not isinstance(arguments, Mapping):
        return _error(
            request_id,
            -32602,
            "tools/call params.arguments must be an object",
        )
    arguments_map = cast("Mapping[str, object]", arguments)
    try:
        payload = dispatch_tool(name, dict(arguments_map))
    except Exception as exc:  # noqa: BLE001
        return _result(
            request_id,
            {
                "content": [{"type": "text", "text": str(exc)}],
                "isError": True,
            },
        )
    return _result(
        request_id,
        {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(payload, sort_keys=True),
                },
            ],
            "isError": False,
        },
    )


def _initialize_result() -> JsonObject:
    return {
        "protocolVersion": "2024-11-05",
        "capabilities": {"tools": {}},
        "serverInfo": {"name": "oh-my-field", "version": "0.1.0"},
    }


def _result(request_id: JsonValue, result: object) -> JsonObject:
    return {"jsonrpc": "2.0", "id": request_id, "result": cast("JsonValue", result)}


def _error(request_id: JsonValue, code: int, message: str) -> JsonObject:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": code, "message": message},
    }


def _json_id(value: object) -> JsonValue:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    return None
