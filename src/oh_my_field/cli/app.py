import typer

from oh_my_field.cli.commands import (
    capability,
    capture,
    context,
    dashboard,
    diagnostics,
    evaluate,
    export,
    health,
    import_run,
    inspect_artifact,
    learn,
    orchestrate,
    promote,
    reflect,
    registry,
    replay,
    review,
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


def _main() -> None:
    pass


app.callback()(_main)

diagnostics.register(app)
capture.register(app)
import_run.register(app)
promote.register(app)
health.register(app)
capability.register(capability_app)
replay.register(app)
evaluate.register(app)
review.register(app)
learn.register(app)
verify.register(app)
context.register(app)
orchestrate.register(app)
dashboard.register(app)
registry.register(app)
reflect.register(app)
inspect_artifact.register(app)
export.register(app)
