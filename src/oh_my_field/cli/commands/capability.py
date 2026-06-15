from pathlib import Path
from typing import Annotated, Literal

import typer

from oh_my_field.cli.errors import cli_errors
from oh_my_field.cli.output import emit_json
from oh_my_field.domain.layout import (
    DEFAULT_CAPABILITIES_DIR,
    DEFAULT_EVAL_DIR,
)
from oh_my_field.domain.models import StrictModel
from oh_my_field.infrastructure.portability.bundle_store import (
    prepare_bundle_for_import,
    verify_package_manifest,
)
from oh_my_field.portability import (
    CapabilityAdaptRequest,
    CapabilityPortabilityExportRequest,
    CapabilityPortabilityImportRequest,
    CapabilityRemapRequest,
    CapabilityValidationRequest,
    PortabilityError,
    adapt_capability_package,
    export_capability_package,
    import_capability_package,
    remap_capability_package,
    validate_capability_package,
)

TargetRuntime = Literal["codex", "claude_code", "hermes", "pi", "odysseus", "generic"]


class CapabilityUnpackOutput(StrictModel):
    package_path: str
    unpacked_path: str | None = None
    status: Literal["pass", "fail"]
    errors: tuple[str, ...] = ()


def capability_export(
    capability_name: Annotated[str, typer.Argument()],
    target: Annotated[TargetRuntime, typer.Option("--target")],
    out: Annotated[Path, typer.Option("--out")],
    target_model: Annotated[str | None, typer.Option("--target-model")] = None,
    target_project: Annotated[str | None, typer.Option("--target-project")] = None,
    source_project: Annotated[str | None, typer.Option("--source-project")] = None,
    source_reasoning_effort: Annotated[
        str | None,
        typer.Option("--source-reasoning-effort"),
    ] = None,
    source_context_tokens: Annotated[
        int | None,
        typer.Option("--source-context-tokens"),
    ] = None,
    target_context_tokens: Annotated[
        int | None,
        typer.Option("--target-context-tokens"),
    ] = None,
    include_evidence: Annotated[
        Literal["none", "summary", "redacted", "full"],
        typer.Option("--include-evidence"),
    ] = "summary",
    skill_style: Annotated[
        Literal["launcher", "full"],
        typer.Option("--skill-style"),
    ] = "launcher",
    bundle_format: Annotated[
        Literal["archive", "dir"],
        typer.Option("--format"),
    ] = "archive",
    capabilities_dir: Annotated[
        Path, typer.Option("--capabilities-dir")
    ] = DEFAULT_CAPABILITIES_DIR,
    evidence_dir: Annotated[Path, typer.Option("--evidence-dir")] = Path(
        ".omf/evidence",
    ),
) -> None:
    with cli_errors(PortabilityError):
        request = CapabilityPortabilityExportRequest(
            capability_name=capability_name,
            target=target,
            target_model=target_model,
            target_project=target_project,
            source_project=source_project,
            source_reasoning_effort=source_reasoning_effort,
            source_context_tokens=source_context_tokens,
            target_context_tokens=target_context_tokens,
            include_evidence=include_evidence,
            skill_style=skill_style,
            bundle_format=bundle_format,
            out=out,
            capabilities_dir=capabilities_dir,
            evidence_dir=evidence_dir,
        )
        summary = export_capability_package(request)
        emit_json(summary)


def capability_import(
    bundle_path: Annotated[Path, typer.Argument()],
    runtime: Annotated[TargetRuntime | None, typer.Option("--runtime")] = None,
    model: Annotated[str | None, typer.Option("--model")] = None,
    project: Annotated[str | None, typer.Option("--project")] = None,
    validate: Annotated[bool, typer.Option("--validate")] = False,
    available_tool: Annotated[
        list[str] | None,
        typer.Option("--available-tool"),
    ] = None,
    as_name: Annotated[str | None, typer.Option("--as")] = None,
    namespace: Annotated[str | None, typer.Option("--namespace")] = None,
    if_exists: Annotated[
        Literal["fail", "merge", "version", "overwrite"],
        typer.Option("--if-exists"),
    ] = "fail",
    import_dir: Annotated[Path, typer.Option("--import-dir")] = Path(".omf/imports"),
    capabilities_dir: Annotated[
        Path, typer.Option("--capabilities-dir")
    ] = DEFAULT_CAPABILITIES_DIR,
    eval_dir: Annotated[Path, typer.Option("--eval-dir")] = DEFAULT_EVAL_DIR,
    evidence_dir: Annotated[Path, typer.Option("--evidence-dir")] = Path(
        ".omf/evidence",
    ),
) -> None:
    with cli_errors(PortabilityError):
        request = CapabilityPortabilityImportRequest(
            bundle_path=bundle_path,
            import_dir=import_dir,
            capabilities_dir=capabilities_dir,
            eval_dir=eval_dir,
            evidence_dir=evidence_dir,
            runtime=runtime,
            model=model,
            project=project,
            validate_import=validate,
            available_tools=tuple(available_tool or ()),
            as_name=as_name,
            namespace=namespace,
            if_exists=if_exists,
        )
        summary = import_capability_package(request)
        emit_json(summary)


def capability_unpack(
    package_path: Annotated[Path, typer.Argument()],
    out: Annotated[Path, typer.Option("--out")] = Path(".omf/imports"),
) -> None:
    with cli_errors(PortabilityError):
        _, unpacked = prepare_bundle_for_import(package_path, out)
        target = unpacked or package_path
        ok, errors = verify_package_manifest(target)
        emit_json(
            CapabilityUnpackOutput(
                package_path=str(package_path),
                unpacked_path=None if unpacked is None else str(unpacked),
                status="pass" if ok else "fail",
                errors=errors,
            ),
        )
        if not ok:
            raise typer.Exit(code=1)


def capability_validate(
    capability_name: Annotated[str, typer.Argument()],
    target: Annotated[TargetRuntime, typer.Option("--target")],
    model: Annotated[str | None, typer.Option("--model")] = None,
    project: Annotated[str | None, typer.Option("--project")] = None,
    available_tool: Annotated[
        list[str] | None,
        typer.Option("--available-tool"),
    ] = None,
    run_command: Annotated[str | None, typer.Option("--run-command")] = None,
    run_argv: Annotated[list[str] | None, typer.Option("--run-argv")] = None,
    expected_artifact: Annotated[
        list[str] | None,
        typer.Option("--expected-artifact"),
    ] = None,
    command_cwd: Annotated[Path, typer.Option("--command-cwd")] = Path(),
    command_timeout_seconds: Annotated[
        int,
        typer.Option("--command-timeout-seconds"),
    ] = 600,
    approve_command_risk: Annotated[
        bool,
        typer.Option("--approve-command-risk"),
    ] = False,
    require_cwd_inside_project: Annotated[
        bool,
        typer.Option("--require-cwd-inside-project"),
    ] = False,
    allow_env: Annotated[list[str] | None, typer.Option("--allow-env")] = None,
    capabilities_dir: Annotated[
        Path, typer.Option("--capabilities-dir")
    ] = DEFAULT_CAPABILITIES_DIR,
    eval_dir: Annotated[Path, typer.Option("--eval-dir")] = DEFAULT_EVAL_DIR,
    evidence_dir: Annotated[Path, typer.Option("--evidence-dir")] = Path(
        ".omf/evidence",
    ),
) -> None:
    with cli_errors(PortabilityError):
        request = CapabilityValidationRequest(
            capability_name=capability_name,
            capabilities_dir=capabilities_dir,
            eval_dir=eval_dir,
            evidence_dir=evidence_dir,
            target=target,
            model=model,
            project=project,
            available_tools=tuple(available_tool or ()),
            run_command=run_command,
            run_argv=tuple(run_argv or ()),
            expected_artifacts=tuple(expected_artifact or ()),
            command_cwd=command_cwd,
            command_timeout_seconds=command_timeout_seconds,
            approve_command_risk=approve_command_risk,
            require_cwd_inside_project=require_cwd_inside_project,
            allow_env=tuple(allow_env or ()),
        )
        summary = validate_capability_package(request)
        emit_json(summary)


def _parse_map(items: list[str] | None) -> tuple[tuple[str, str], ...]:
    pairs: list[tuple[str, str]] = []
    for item in items or []:
        key, separator, value = item.partition("=")
        if not separator or not key or not value:
            msg = f"--map expects key=value, got {item!r}"
            raise typer.BadParameter(msg)
        pairs.append((key, value))
    return tuple(pairs)


def capability_remap(
    capability_name: Annotated[str, typer.Argument()],
    target: Annotated[TargetRuntime, typer.Option("--target")],
    model: Annotated[str | None, typer.Option("--model")] = None,
    target_project: Annotated[str | None, typer.Option("--target-project")] = None,
    map_: Annotated[list[str] | None, typer.Option("--map")] = None,
    unresolved: Annotated[list[str] | None, typer.Option("--unresolved")] = None,
    capabilities_dir: Annotated[
        Path, typer.Option("--capabilities-dir")
    ] = DEFAULT_CAPABILITIES_DIR,
) -> None:
    with cli_errors(PortabilityError):
        request = CapabilityRemapRequest(
            capability_name=capability_name,
            capabilities_dir=capabilities_dir,
            target=target,
            model=model,
            target_project=target_project,
            mappings=_parse_map(map_),
            unresolved=tuple(unresolved or ()),
        )
        summary = remap_capability_package(request)
        emit_json(summary)


def capability_adapt(
    capability_name: Annotated[str, typer.Argument()],
    target: Annotated[TargetRuntime, typer.Option("--target")],
    model: Annotated[str | None, typer.Option("--model")] = None,
    instruction_variant: Annotated[
        Literal["base", "compact"] | None,
        typer.Option("--instruction-variant"),
    ] = None,
    context_variant: Annotated[
        Literal["full", "compressed"] | None,
        typer.Option("--context-variant"),
    ] = None,
    require_human_review: Annotated[
        bool | None,
        typer.Option("--require-human-review/--no-require-human-review"),
    ] = None,
    capabilities_dir: Annotated[
        Path, typer.Option("--capabilities-dir")
    ] = DEFAULT_CAPABILITIES_DIR,
) -> None:
    with cli_errors(PortabilityError):
        request = CapabilityAdaptRequest(
            capability_name=capability_name,
            capabilities_dir=capabilities_dir,
            target=target,
            model=model,
            instruction_variant=instruction_variant,
            context_variant=context_variant,
            require_human_review=require_human_review,
        )
        summary = adapt_capability_package(request)
        emit_json(summary)


def register(capability_app: typer.Typer) -> None:
    capability_app.command(
        "export",
        help="Export a capability package for a target runtime/model.",
    )(capability_export)
    capability_app.command(
        "import",
        help=(
            "Import a portable capability package and write a target validation report."
        ),
    )(capability_import)
    capability_app.command(
        "unpack",
        help="Safely unpack an OMF capability archive without importing it.",
    )(capability_unpack)
    capability_app.command(
        "validate",
        help="Re-validate an imported capability against its target runtime.",
    )(capability_validate)
    capability_app.command(
        "remap",
        help="Record a context remap plan for an imported target.",
    )(capability_remap)
    capability_app.command(
        "adapt",
        help="Apply instruction/context/review overrides to an imported target.",
    )(capability_adapt)
