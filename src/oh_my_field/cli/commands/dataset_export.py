from pathlib import Path
from typing import Annotated, Literal

import typer

from oh_my_field.application.dataset_export import (
    DatasetExportError,
    DatasetExportRequest,
    run_dataset_export,
)
from oh_my_field.cli.errors import cli_errors
from oh_my_field.cli.output import emit_json

DatasetTypeOption = Literal["all", "fine-tuning", "preference", "eval"]


def dataset_export(
    capability_name: Annotated[str, typer.Argument()],
    dataset_type: Annotated[
        DatasetTypeOption,
        typer.Option("--dataset-type"),
    ] = "all",
    learning_dir: Annotated[Path, typer.Option("--learning-dir")] = Path(
        ".omf/learning",
    ),
    learning_patch_dir: Annotated[
        Path,
        typer.Option("--learning-patch-dir"),
    ] = Path(".omf/learning_patches"),
    eval_dir: Annotated[Path, typer.Option("--eval-dir")] = Path(".omf/evals"),
    output_dir: Annotated[Path, typer.Option("--output-dir")] = Path(
        ".omf/datasets",
    ),
) -> None:
    with cli_errors(DatasetExportError):
        summary = run_dataset_export(
            DatasetExportRequest(
                capability_name=capability_name,
                dataset_type=dataset_type,
                learning_dir=learning_dir,
                learning_patch_dir=learning_patch_dir,
                eval_dir=eval_dir,
                output_dir=output_dir,
            ),
        )
        emit_json(summary)


def register(app: typer.Typer) -> None:
    app.command(
        "dataset-export",
        help="Export learning and eval artifacts as JSONL datasets.",
    )(dataset_export)
