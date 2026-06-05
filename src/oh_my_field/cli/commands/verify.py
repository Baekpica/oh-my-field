from pathlib import Path
from typing import Annotated, Literal

import typer

from oh_my_field.application.verify import (
    VerifyError,
    VerifyRequest,
    verify_artifact,
)
from oh_my_field.cli.errors import cli_errors
from oh_my_field.cli.output import emit_json
from oh_my_field.domain.layout import (
    DEFAULT_CAPABILITIES_DIR,
    DEFAULT_CONTEXT_DIR,
    DEFAULT_EVAL_DIR,
    DEFAULT_EXPORTS_DIR,
    DEFAULT_LEARNING_PATCH_DIR,
    DEFAULT_REVIEW_DIR,
)


def verify(
    target_type: Annotated[
        Literal[
            "evidence",
            "capability",
            "replay",
            "eval",
            "context",
            "learning",
            "learning_patch",
            "reflection",
            "review",
            "export",
        ],
        typer.Argument(),
    ],
    target_id: Annotated[str, typer.Argument()],
    capabilities_dir: Annotated[
        Path, typer.Option("--capabilities-dir")
    ] = DEFAULT_CAPABILITIES_DIR,
    evidence_dir: Annotated[Path, typer.Option("--evidence-dir")] = Path(
        ".omf/evidence",
    ),
    replay_dir: Annotated[Path, typer.Option("--replay-dir")] = Path(
        ".omf/replays",
    ),
    eval_dir: Annotated[Path, typer.Option("--eval-dir")] = DEFAULT_EVAL_DIR,
    context_dir: Annotated[Path, typer.Option("--context-dir")] = DEFAULT_CONTEXT_DIR,
    learning_dir: Annotated[Path, typer.Option("--learning-dir")] = Path(
        ".omf/learning",
    ),
    learning_patch_dir: Annotated[
        Path,
        typer.Option("--learning-patch-dir"),
    ] = DEFAULT_LEARNING_PATCH_DIR,
    reflection_dir: Annotated[Path, typer.Option("--reflection-dir")] = Path(
        ".omf/reflections",
    ),
    review_dir: Annotated[Path, typer.Option("--review-dir")] = DEFAULT_REVIEW_DIR,
    export_dir: Annotated[Path, typer.Option("--export-dir")] = DEFAULT_EXPORTS_DIR,
) -> None:
    with cli_errors(VerifyError):
        request = VerifyRequest(
            target_type=target_type,
            target_id=target_id,
            capabilities_dir=capabilities_dir,
            evidence_dir=evidence_dir,
            replay_dir=replay_dir,
            eval_dir=eval_dir,
            context_dir=context_dir,
            learning_dir=learning_dir,
            learning_patch_dir=learning_patch_dir,
            reflection_dir=reflection_dir,
            review_dir=review_dir,
            export_dir=export_dir,
        )
        result = verify_artifact(request)
        emit_json(result)
        if result.status == "fail":
            raise typer.Exit(code=1)


def register(app: typer.Typer) -> None:
    app.command("verify", help="Verify artifact integrity chain hashes.")(verify)
