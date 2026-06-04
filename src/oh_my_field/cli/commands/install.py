from pathlib import Path
from typing import Annotated, Literal

import typer

from oh_my_field.application.install import install_mcp_config, install_omf_skill
from oh_my_field.cli.output import emit_json
from oh_my_field.domain.skill.models import SkillInstallRequest
from oh_my_field.mcp.schemas import McpInstallRequest

TargetRuntime = Literal["codex", "claude_code", "hermes", "generic"]
McpClient = Literal["generic"]


def install_skill(
    runtime: Annotated[TargetRuntime, typer.Option("--runtime")],
    project: Annotated[Path, typer.Option("--project")] = Path(),
    profile: Annotated[str | None, typer.Option("--profile")] = None,
    out: Annotated[Path, typer.Option("--out")] = Path(".omf/agent/omf-skill"),
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
    overwrite: Annotated[bool, typer.Option("--overwrite")] = False,
) -> None:
    summary = install_omf_skill(
        SkillInstallRequest(
            runtime=runtime,
            project=project,
            profile=profile,
            out=out,
            dry_run=dry_run,
            overwrite=overwrite,
        ),
    )
    emit_json(summary)


def install_mcp(
    client: Annotated[McpClient, typer.Option("--client")],
    project: Annotated[Path, typer.Option("--project")] = Path(),
    out: Annotated[Path, typer.Option("--out")] = Path(".omf/mcp.json"),
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
    overwrite: Annotated[bool, typer.Option("--overwrite")] = False,
) -> None:
    summary = install_mcp_config(
        McpInstallRequest(
            client=client,
            project=project,
            out=out,
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
