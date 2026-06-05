import json
import shutil
import tomllib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, cast

import yaml

McpPatchAction = Literal["write", "skip_existing", "plan_only"]


class McpConfigPatchError(ValueError):
    """Raised when an MCP config file cannot be patched safely."""


@dataclass(frozen=True, slots=True)
class McpServerConfig:
    command: str
    args: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class McpConfigPatchResult:
    config_path: Path
    backup_path: Path | None
    action: McpPatchAction
    source: str
    reason: str

    @property
    def wrote(self) -> bool:
        return self.action == "write"


@dataclass(frozen=True, slots=True)
class McpConfigPatchRequest:
    config_path: Path
    server_name: str
    server: McpServerConfig
    dry_run: bool
    overwrite: bool
    source: str


def patch_json_mcp_config(
    *,
    request: McpConfigPatchRequest,
) -> McpConfigPatchResult:
    data = _load_json_mapping(request.config_path)
    servers = data.get("mcpServers")
    if servers is None:
        servers = {}
    if not isinstance(servers, dict):
        msg = "mcpServers must be a JSON object"
        raise McpConfigPatchError(msg)
    server_map = cast("dict[str, object]", servers)
    if request.server_name in server_map and not request.overwrite:
        return _skip_result(config_path=request.config_path, source=request.source)
    next_data = dict(data)
    next_servers = dict(server_map)
    next_servers[request.server_name] = _server_json(request.server)
    next_data["mcpServers"] = next_servers
    content = json.dumps(next_data, indent=2, sort_keys=False) + "\n"
    return _write_result(
        config_path=request.config_path,
        content=content,
        dry_run=request.dry_run,
        source=request.source,
    )


def patch_yaml_mcp_config(
    *,
    request: McpConfigPatchRequest,
) -> McpConfigPatchResult:
    data = _load_yaml_mapping(request.config_path)
    servers = data.get("mcp_servers")
    if servers is None:
        servers = {}
    if not isinstance(servers, dict):
        msg = "mcp_servers must be a YAML mapping"
        raise McpConfigPatchError(msg)
    server_map = cast("dict[str, object]", servers)
    if request.server_name in server_map and not request.overwrite:
        return _skip_result(config_path=request.config_path, source=request.source)
    next_data = dict(data)
    next_servers = dict(server_map)
    next_servers[request.server_name] = _server_json(request.server)
    next_data["mcp_servers"] = next_servers
    content = yaml.safe_dump(next_data, sort_keys=False)
    return _write_result(
        config_path=request.config_path,
        content=content,
        dry_run=request.dry_run,
        source=request.source,
    )


def patch_toml_mcp_config(
    *,
    request: McpConfigPatchRequest,
) -> McpConfigPatchResult:
    config_path = request.config_path
    existing = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
    try:
        data = tomllib.loads(existing or "")
    except tomllib.TOMLDecodeError as exc:
        msg = f"invalid TOML MCP config at {config_path}"
        raise McpConfigPatchError(msg) from exc
    servers = data.get("mcp_servers")
    if servers is None:
        servers = {}
    if not isinstance(servers, dict):
        msg = "mcp_servers must be a TOML table"
        raise McpConfigPatchError(msg)
    server_map = cast("dict[str, object]", servers)
    if request.server_name in server_map and not request.overwrite:
        return _skip_result(config_path=config_path, source=request.source)
    table = f"mcp_servers.{request.server_name}"
    content = _append_toml_table(
        _remove_toml_table(existing, table) if request.overwrite else existing,
        table=table,
        server=request.server,
    )
    return _write_result(
        config_path=config_path,
        content=content,
        dry_run=request.dry_run,
        source=request.source,
    )


def _load_json_mapping(config_path: Path) -> dict[str, object]:
    if not config_path.exists():
        return {}
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        msg = f"invalid JSON MCP config at {config_path}"
        raise McpConfigPatchError(msg) from exc
    if not isinstance(data, dict):
        msg = "MCP JSON config root must be an object"
        raise McpConfigPatchError(msg)
    return cast("dict[str, object]", data)


def _load_yaml_mapping(config_path: Path) -> dict[str, object]:
    if not config_path.exists():
        return {}
    try:
        data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        msg = f"invalid YAML MCP config at {config_path}"
        raise McpConfigPatchError(msg) from exc
    if data is None:
        return {}
    if not isinstance(data, dict):
        msg = "MCP YAML config root must be a mapping"
        raise McpConfigPatchError(msg)
    return cast("dict[str, object]", data)


def _server_json(server: McpServerConfig) -> dict[str, object]:
    return {"command": server.command, "args": list(server.args)}


def _skip_result(*, config_path: Path, source: str) -> McpConfigPatchResult:
    return McpConfigPatchResult(
        config_path=config_path,
        backup_path=None,
        action="skip_existing",
        source=source,
        reason="server exists and overwrite is false",
    )


def _write_result(
    *,
    config_path: Path,
    content: str,
    dry_run: bool,
    source: str,
) -> McpConfigPatchResult:
    if dry_run:
        return McpConfigPatchResult(
            config_path=config_path,
            backup_path=None,
            action="plan_only",
            source=source,
            reason="dry-run requested",
        )
    backup_path = _backup_existing(config_path)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(content, encoding="utf-8")
    return McpConfigPatchResult(
        config_path=config_path,
        backup_path=backup_path,
        action="write",
        source=source,
        reason="MCP config patched",
    )


def _backup_existing(config_path: Path) -> Path | None:
    if not config_path.exists():
        return None
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    backup_path = config_path.with_name(f"{config_path.name}.bak-{timestamp}")
    shutil.copy2(config_path, backup_path)
    return backup_path


def _remove_toml_table(content: str, table: str) -> str:
    lines = content.splitlines()
    kept: list[str] = []
    skip = False
    table_header = f"[{table}]"
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            if stripped == table_header:
                skip = True
                continue
            if skip:
                skip = False
        if not skip:
            kept.append(line)
    return "\n".join(kept).rstrip()


def _append_toml_table(content: str, *, table: str, server: McpServerConfig) -> str:
    prefix = content.rstrip()
    block = "\n".join(
        [
            f"[{table}]",
            f"command = {json.dumps(server.command)}",
            f"args = {_toml_string_array(server.args)}",
            "",
        ],
    )
    if not prefix:
        return block
    return f"{prefix}\n\n{block}"


def _toml_string_array(values: tuple[str, ...]) -> str:
    return "[" + ", ".join(json.dumps(value) for value in values) + "]"
