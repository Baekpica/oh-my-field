from typing import Annotated

import typer

from oh_my_field.cli.commands import (
    capability,
    capture,
    context,
    dashboard,
    dataset_export,
    diagnostics,
    diff_artifacts,
    evaluate,
    explain,
    export,
    health,
    import_run,
    init_field,
    inspect_artifact,
    install,
    learn,
    mcp,
    orchestrate,
    promote,
    reflect,
    registry,
    replay,
    review,
    session,
    verify,
)

app = typer.Typer(
    help="oh-my-field turns tacit know-how into reusable capabilities.",
    no_args_is_help=True,
)
capability_app = typer.Typer(
    help="Export and import portable capability packages.",
    no_args_is_help=True,
)
app.add_typer(capability_app, name="capability")
install_app = typer.Typer(help="Install OMF agent activation resources.")
app.add_typer(install_app, name="install")
session_app = typer.Typer(help="Track active agent work as OMF sessions.")
app.add_typer(session_app, name="session")
mcp_app = typer.Typer(help="Run OMF MCP server surfaces.")
app.add_typer(mcp_app, name="mcp")


def _main(
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            help="Print package and schema version information.",
            is_eager=True,
        ),
    ] = False,
) -> None:
    if version:
        diagnostics.version()
        raise typer.Exit


app.callback(invoke_without_command=True)(_main)

diagnostics.register(app)
capture.register(app)
init_field.register(app)
import_run.register(app)
diff_artifacts.register(app)
explain.register(app)
promote.register(app)
health.register(app)
capability.register(capability_app)
install.register(install_app)
replay.register(app)
evaluate.register(app)
review.register(app)
learn.register(app)
verify.register(app)
context.register(app)
orchestrate.register(app)
dashboard.register(app)
dataset_export.register(app)
registry.register(app)
reflect.register(app)
inspect_artifact.register(app)
export.register(app)
session.register(session_app)
mcp.register(mcp_app)
