from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from omf.storage import (
    CaptureRequest,
    OmfError,
    capture_evidence,
    evaluate_capability,
    export_learning_items,
    inspect_json_artifact,
    list_store,
    promote_evidence,
    record_regression_case,
    record_review,
    replay_capability,
    search_store,
)

app = typer.Typer(add_completion=False, pretty_exceptions_enable=False)


def echo_json(payload: str) -> None:
    typer.echo(payload)


@app.command()
def capture(
    goal: Annotated[str, typer.Option("--goal", help="Goal proven by this run.")],
    command: Annotated[str, typer.Option("--command", help="Command to execute.")],
    artifact: Annotated[
        list[str] | None,
        typer.Option("--artifact", help="Artifact path to hash after command execution."),
    ] = None,
    check: Annotated[
        list[str] | None,
        typer.Option("--check", help="Harness command to run after the main command."),
    ] = None,
    store_dir: Annotated[
        str,
        typer.Option("--store-dir", help="Local omf store directory."),
    ] = ".omf",
    cwd: Annotated[str, typer.Option("--cwd", help="Working directory for the command.")] = ".",
) -> None:
    try:
        evidence, evidence_path = capture_evidence(
            CaptureRequest(
                goal=goal,
                command=command,
                artifacts=tuple(artifact or ()),
                store_dir=Path(store_dir),
                cwd=Path(cwd),
                checks=tuple(check or ()),
            )
        )
    except OmfError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=1) from None

    output = evidence.model_dump()
    output["evidence_path"] = str(evidence_path.resolve())
    echo_json(json.dumps(output, indent=2))


@app.command()
def promote(
    evidence_path: Annotated[Path, typer.Argument(help="Evidence JSON path to promote.")],
    name: Annotated[str, typer.Option("--name", help="Capability name.")],
    store_dir: Annotated[
        str,
        typer.Option("--store-dir", help="Local omf store directory."),
    ] = ".omf",
) -> None:
    try:
        manifest, manifest_path = promote_evidence(
            evidence_path=evidence_path,
            name=name,
            store_dir=Path(store_dir),
        )
    except OmfError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=1) from None

    output = manifest.model_dump()
    output["manifest_path"] = str(manifest_path.resolve())
    echo_json(json.dumps(output, indent=2))


@app.command()
def replay(
    manifest_path: Annotated[Path, typer.Argument(help="Capability manifest JSON path.")],
    store_dir: Annotated[
        str,
        typer.Option("--store-dir", help="Local omf store directory."),
    ] = ".omf",
) -> None:
    try:
        replay_result, replay_path = replay_capability(
            manifest_path=manifest_path,
            store_dir=Path(store_dir),
        )
    except OmfError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=1) from None

    output = replay_result.model_dump()
    output["replay_path"] = str(replay_path.resolve())
    echo_json(json.dumps(output, indent=2))
    if replay_result.status != "pass":
        raise typer.Exit(code=1)


@app.command(name="eval")
def eval_command(
    manifest_path: Annotated[Path, typer.Argument(help="Capability manifest JSON path.")],
    runs: Annotated[int, typer.Option("--runs", help="Number of replay runs.")] = 1,
    store_dir: Annotated[
        str,
        typer.Option("--store-dir", help="Local omf store directory."),
    ] = ".omf",
) -> None:
    try:
        eval_result, eval_path = evaluate_capability(
            manifest_path=manifest_path,
            store_dir=Path(store_dir),
            runs=runs,
        )
    except OmfError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=1) from None

    output = eval_result.model_dump()
    output["eval_path"] = str(eval_path.resolve())
    echo_json(json.dumps(output, indent=2))
    if eval_result.status != "pass":
        raise typer.Exit(code=1)


@app.command(name="list")
def list_command(
    store_dir: Annotated[
        str,
        typer.Option("--store-dir", help="Local omf store directory."),
    ] = ".omf",
) -> None:
    try:
        index = list_store(Path(store_dir))
    except OmfError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=1) from None

    echo_json(json.dumps(index.model_dump(), indent=2))


@app.command()
def inspect(
    artifact_path: Annotated[Path, typer.Argument(help="omf JSON artifact path.")],
) -> None:
    try:
        result = inspect_json_artifact(artifact_path)
    except OmfError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=1) from None

    echo_json(json.dumps(result.model_dump(), indent=2))


@app.command()
def review(
    artifact_path: Annotated[Path, typer.Argument(help="omf JSON artifact path to review.")],
    reviewer: Annotated[str, typer.Option("--reviewer", help="Reviewer identifier.")],
    decision: Annotated[
        str,
        typer.Option(
            "--decision",
            help=(
                "Review decision: approve, reject, revise, add_context, change_goal, "
                "change_constraint, mark_reusable, mark_unsafe, create_regression_case."
            ),
        ),
    ],
    note: Annotated[str, typer.Option("--note", help="Evidence-backed review note.")],
    store_dir: Annotated[
        str,
        typer.Option("--store-dir", help="Local omf store directory."),
    ] = ".omf",
) -> None:
    try:
        result, review_path = record_review(
            artifact_path=artifact_path,
            reviewer=reviewer,
            decision=decision,
            note=note,
            store_dir=Path(store_dir),
        )
    except OmfError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=1) from None

    output = result.model_dump()
    output["review_path"] = str(review_path.resolve())
    echo_json(json.dumps(output, indent=2))


@app.command()
def regress(
    manifest_path: Annotated[Path, typer.Argument(help="Capability manifest JSON path.")],
    source_artifact: Annotated[
        Path,
        typer.Option(
            "--source-artifact",
            help="omf JSON artifact that motivated this regression case.",
        ),
    ],
    name: Annotated[str, typer.Option("--name", help="Regression case name.")],
    reason: Annotated[
        str,
        typer.Option("--reason", help="Evidence-backed reason for this regression case."),
    ],
    store_dir: Annotated[
        str,
        typer.Option("--store-dir", help="Local omf store directory."),
    ] = ".omf",
) -> None:
    try:
        result, regression_path = record_regression_case(
            manifest_path=manifest_path,
            source_artifact_path=source_artifact,
            name=name,
            reason=reason,
            store_dir=Path(store_dir),
        )
    except OmfError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=1) from None

    output = result.model_dump()
    output["regression_path"] = str(regression_path.resolve())
    echo_json(json.dumps(output, indent=2))
    if result.status != "pass":
        raise typer.Exit(code=1)


@app.command()
def learn(
    source_artifact: Annotated[
        list[Path],
        typer.Option(
            "--source-artifact",
            help="omf JSON artifact to include in the learning export.",
        ),
    ],
    name: Annotated[str, typer.Option("--name", help="Learning export name.")],
    purpose: Annotated[
        str,
        typer.Option(
            "--purpose",
            help="Learning purpose: prompt_improvement, eval_set, fine_tuning_candidate.",
        ),
    ],
    note: Annotated[
        str,
        typer.Option("--note", help="Evidence-backed note applied to exported rows."),
    ],
    store_dir: Annotated[
        str,
        typer.Option("--store-dir", help="Local omf store directory."),
    ] = ".omf",
) -> None:
    try:
        result, manifest_path = export_learning_items(
            source_artifact_paths=tuple(source_artifact),
            name=name,
            purpose=purpose,
            note=note,
            store_dir=Path(store_dir),
        )
    except OmfError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=1) from None

    output = result.model_dump()
    output["manifest_path"] = str(manifest_path.resolve())
    echo_json(json.dumps(output, indent=2))


@app.command()
def search(
    query: Annotated[str, typer.Argument(help="Text query to search in local omf artifacts.")],
    kind: Annotated[
        str | None,
        typer.Option(
            "--kind",
            help=(
                "Optional artifact kind: evidence, capability, replay, eval, "
                "review, regression, learning."
            ),
        ),
    ] = None,
    store_dir: Annotated[
        str,
        typer.Option("--store-dir", help="Local omf store directory."),
    ] = ".omf",
) -> None:
    try:
        result = search_store(Path(store_dir), query, kind=kind)
    except OmfError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=1) from None

    echo_json(json.dumps(result.model_dump(), indent=2))


def main() -> None:
    app()


if __name__ == "__main__":
    main()
