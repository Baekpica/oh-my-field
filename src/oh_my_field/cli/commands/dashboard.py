from pathlib import Path
from typing import Annotated, cast

import typer
from pydantic import ValidationError

from oh_my_field.domain.layout import (
    DEFAULT_CAPABILITIES_DIR,
    DEFAULT_EVAL_DIR,
    DEFAULT_LEARNING_PATCH_DIR,
)
from oh_my_field.infrastructure.dashboard.server import (
    DEFAULT_DASHBOARD_PORT,
    DashboardError,
    DashboardPaths,
    DashboardServeRequest,
    build_dashboard_snapshot,
    create_dashboard_server,
)
from oh_my_field.infrastructure.fs.storage import StorageError


def dashboard(
    host: Annotated[str, typer.Option("--host")] = "127.0.0.1",
    port: Annotated[int, typer.Option("--port")] = DEFAULT_DASHBOARD_PORT,
    once: Annotated[bool, typer.Option("--once")] = False,
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
    workflow_dir: Annotated[Path, typer.Option("--workflow-dir")] = Path(
        ".omf/workflows",
    ),
    review_dir: Annotated[Path, typer.Option("--review-dir")] = Path(
        ".omf/reviews",
    ),
    eval_set_dir: Annotated[Path, typer.Option("--eval-set-dir")] = Path(
        ".omf/eval_sets",
    ),
    learning_patch_dir: Annotated[
        Path,
        typer.Option("--learning-patch-dir"),
    ] = DEFAULT_LEARNING_PATCH_DIR,
) -> None:
    paths = DashboardPaths(
        capabilities_dir=capabilities_dir,
        evidence_dir=evidence_dir,
        replay_dir=replay_dir,
        eval_dir=eval_dir,
        workflow_dir=workflow_dir,
        review_dir=review_dir,
        eval_set_dir=eval_set_dir,
        learning_patch_dir=learning_patch_dir,
    )
    try:
        if once:
            typer.echo(build_dashboard_snapshot(paths).model_dump_json())
            return
        server = create_dashboard_server(
            DashboardServeRequest(host=host, port=port, paths=paths),
        )
    except (DashboardError, OSError, StorageError, ValidationError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    address = cast("tuple[str, int]", server.server_address)
    typer.echo(f"Serving dashboard at http://{address[0]}:{address[1]}")
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        return
    finally:
        server.server_close()


def register(app: typer.Typer) -> None:
    app.command(
        "dashboard",
        help="Serve or print the local operating dashboard.",
    )(dashboard)
