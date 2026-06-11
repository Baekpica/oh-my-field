from pathlib import Path
from typing import Annotated, Literal

import typer

from oh_my_field.application.conformance import (
    ConformanceError,
    RuntimeConformanceRequest,
    run_runtime_conformance_workflow,
)
from oh_my_field.application.install import install_mcp_config, install_omf_skill
from oh_my_field.application.install.skill_workflow import SkillInstallError
from oh_my_field.cli.errors import cli_errors
from oh_my_field.cli.output import emit_json
from oh_my_field.domain.layout import DEFAULT_CAPABILITIES_DIR
from oh_my_field.domain.models import StrictModel
from oh_my_field.domain.skill.models import SkillInstallRequest, SkillInstallSummary
from oh_my_field.mcp.schemas import McpInstallRequest, McpInstallSummary

AgentRuntime = Literal["codex", "claude_code", "hermes", "pi", "odysseus"]


class RuntimeInstallSummary(StrictModel):
    runtime: AgentRuntime
    skill: SkillInstallSummary
    mcp: McpInstallSummary
    next_action: str


def runtime_conformance(
    runtime: Annotated[AgentRuntime, typer.Argument()],
    project: Annotated[Path, typer.Option("--project")] = Path(),
    home: Annotated[Path | None, typer.Option("--home")] = None,
    capabilities_dir: Annotated[
        Path, typer.Option("--capabilities-dir")
    ] = DEFAULT_CAPABILITIES_DIR,
) -> None:
    with cli_errors(ConformanceError, SkillInstallError):
        summary = run_runtime_conformance_workflow(
            RuntimeConformanceRequest(
                runtime=runtime,
                project=project,
                home=home,
                capabilities_dir=capabilities_dir,
            ),
        )
        emit_json(summary)


def runtime_install(
    runtime: Annotated[AgentRuntime, typer.Argument()],
    project: Annotated[Path, typer.Option("--project")] = Path(),
    home: Annotated[Path | None, typer.Option("--home")] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
    overwrite: Annotated[bool, typer.Option("--overwrite")] = False,
) -> None:
    with cli_errors(SkillInstallError):
        skill = install_omf_skill(
            SkillInstallRequest(
                runtime=runtime,
                project=project,
                home=home,
                dry_run=dry_run,
                overwrite=overwrite,
            ),
        )
        mcp = install_mcp_config(
            McpInstallRequest(
                client=runtime,
                project=project,
                home=home,
                dry_run=dry_run,
                overwrite=overwrite,
            ),
        )
        emit_json(
            RuntimeInstallSummary(
                runtime=runtime,
                skill=skill,
                mcp=mcp,
                next_action=f"run `omf runtime conformance {runtime}` to verify",
            ),
        )


def register(runtime_app: typer.Typer) -> None:
    runtime_app.command(
        "conformance",
        help="Check that an agent runtime follows the OMF adoption surface.",
    )(runtime_conformance)
    runtime_app.command(
        "install",
        help="Install the OMF controller skill and MCP config for a runtime.",
    )(runtime_install)
