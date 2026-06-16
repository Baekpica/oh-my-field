from pathlib import Path
from typing import Annotated, Literal

import typer

from oh_my_field.application.install import install_mcp_config, install_omf_skill
from oh_my_field.application.install.mcp_workflow import McpInstallError
from oh_my_field.application.install.skill_workflow import SkillInstallError
from oh_my_field.cli.errors import cli_errors
from oh_my_field.cli.output import emit_json
from oh_my_field.domain.layout import (
    DEFAULT_AGENT_SKILL_DIR,
    DEFAULT_MCP_CONFIG_PATH,
)
from oh_my_field.domain.skill.models import SkillInstallRequest
from oh_my_field.mcp.schemas import McpInstallRequest

TargetRuntime = Literal[
    "codex", "claude_code", "hermes", "pi", "odysseus", "opencode", "generic"
]
InstallScope = Literal["auto", "user", "project", "export"]
McpClient = Literal[
    "generic", "codex", "claude_code", "hermes", "pi", "odysseus", "opencode"
]


def install_skill(
    runtime: Annotated[TargetRuntime, typer.Option("--runtime")],
    project: Annotated[Path, typer.Option("--project")] = Path(),
    profile: Annotated[str | None, typer.Option("--profile")] = None,
    out: Annotated[Path, typer.Option("--out")] = DEFAULT_AGENT_SKILL_DIR,
    scope: Annotated[InstallScope, typer.Option("--scope")] = "auto",
    home: Annotated[Path | None, typer.Option("--home")] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
    overwrite: Annotated[bool, typer.Option("--overwrite")] = False,
) -> None:
    with cli_errors(SkillInstallError):
        summary = install_omf_skill(
            SkillInstallRequest(
                runtime=runtime,
                project=project,
                profile=profile,
                out=out,
                scope=scope,
                home=home,
                dry_run=dry_run,
                overwrite=overwrite,
            ),
        )
    emit_json(summary)


def install_mcp(
    client: Annotated[McpClient, typer.Option("--client")],
    project: Annotated[Path, typer.Option("--project")] = Path(),
    out: Annotated[Path, typer.Option("--out")] = DEFAULT_MCP_CONFIG_PATH,
    scope: Annotated[InstallScope, typer.Option("--scope")] = "auto",
    home: Annotated[Path | None, typer.Option("--home")] = None,
    server_command: Annotated[str | None, typer.Option("--server-command")] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
    overwrite: Annotated[bool, typer.Option("--overwrite")] = False,
) -> None:
    with cli_errors(McpInstallError):
        summary = install_mcp_config(
            McpInstallRequest(
                client=client,
                project=project,
                out=out,
                scope=scope,
                home=home,
                server_command=server_command,
                dry_run=dry_run,
                overwrite=overwrite,
            ),
        )
    emit_json(summary)


def register(install_app: typer.Typer) -> None:
    install_app.command(
        "skill",
        help="Install the OMF meta-skill for a target agent runtime.",
    )(install_skill)
    install_app.command(
        "mcp",
        help="Install an MCP client config for the OMF stdio server.",
    )(install_mcp)
