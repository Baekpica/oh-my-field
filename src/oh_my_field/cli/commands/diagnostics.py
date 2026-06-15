from typing import Annotated

import typer

from oh_my_field.diagnostics import (
    build_doctor_summary,
    build_version_summary,
    render_doctor_text,
    render_version_text,
)


def version(json_output: Annotated[bool, typer.Option("--json")] = False) -> None:
    summary = build_version_summary()
    typer.echo(
        summary.model_dump_json() if json_output else render_version_text(summary),
    )


def doctor(json_output: Annotated[bool, typer.Option("--json")] = False) -> None:
    summary = build_doctor_summary()
    typer.echo(
        summary.model_dump_json() if json_output else render_doctor_text(summary),
    )


def register(app: typer.Typer) -> None:
    app.command(
        "doctor",
        help="Inspect local OMF installation and runtime availability.",
    )(doctor)
