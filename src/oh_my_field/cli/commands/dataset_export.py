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
from oh_my_field.domain.layout import (
    DEFAULT_EVAL_DIR,
    DEFAULT_LEARNING_PATCH_DIR,
)

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
    ] = DEFAULT_LEARNING_PATCH_DIR,
    eval_dir: Annotated[Path, typer.Option("--eval-dir")] = DEFAULT_EVAL_DIR,
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
