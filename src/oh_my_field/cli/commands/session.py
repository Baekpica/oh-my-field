from pathlib import Path
from typing import Annotated, Literal, cast

import typer

from oh_my_field.application.session import (
    finish_session,
    materialize_session,
    record_session_event,
    start_session,
    suggest_session_capability,
)
from oh_my_field.cli.errors import cli_errors
from oh_my_field.cli.output import emit_json
from oh_my_field.domain.models import CommandRiskCategory, TaskOutcome
from oh_my_field.domain.session.models import (
    AgentSessionEventType,
    SessionActivationSource,
)
from oh_my_field.infrastructure.session.store import (
    SessionExistsError,
    SessionNotFoundError,
    SessionParseError,
)

ActivationSource = Literal["skill", "mcp", "cli", "manual"]
EventType = Literal[
    "goal",
    "assumption",
    "context",
    "command",
    "diff",
    "test_result",
    "artifact",
    "user_feedback",
    "decision",
    "completion",
]
Outcome = Literal["success", "failure", "unknown"]
RiskCategory = Literal[
    "write",
    "destructive",
    "external_call",
    "credential_access",
    "production_write",
    "paid_operation",
]


def session_start(
    runtime: Annotated[str, typer.Option("--runtime")],
    goal: Annotated[str, typer.Option("--goal")],
    model: Annotated[str | None, typer.Option("--model")] = None,
    project_root: Annotated[Path, typer.Option("--project-root")] = Path(),
    activation_source: Annotated[
        ActivationSource,
        typer.Option("--activation-source"),
    ] = "cli",
    sessions_dir: Annotated[Path, typer.Option("--sessions-dir")] = Path(
        ".omf/sessions",
    ),
) -> None:
    with cli_errors(SessionExistsError, SessionNotFoundError, SessionParseError):
        summary = start_session(
            runtime=runtime,
            model=model,
            project_root=project_root,
            activation_source=_activation_source(activation_source),
            goal=goal,
            sessions_dir=sessions_dir,
        )
        emit_json(summary)


def session_event(
    session_id: Annotated[str, typer.Argument()],
    event_type: Annotated[EventType, typer.Option("--type")],
    summary: Annotated[str, typer.Option("--summary")],
    path: Annotated[str | None, typer.Option("--path")] = None,
    command: Annotated[str | None, typer.Option("--command")] = None,
    exit_code: Annotated[int | None, typer.Option("--exit-code")] = None,
    risk_category: Annotated[list[str] | None, typer.Option("--risk-category")] = None,
    sessions_dir: Annotated[Path, typer.Option("--sessions-dir")] = Path(
        ".omf/sessions",
    ),
) -> None:
    with cli_errors(SessionExistsError, SessionNotFoundError, SessionParseError):
        event_summary = record_session_event(
            session_id=session_id,
            event_type=_event_type(event_type),
            summary=summary,
            path=path,
            command=command,
            exit_code=exit_code,
            risk_categories=_risk_categories(risk_category),
            sessions_dir=sessions_dir,
        )
        emit_json(event_summary)


def session_finish(
    session_id: Annotated[str, typer.Argument()],
    outcome: Annotated[Outcome, typer.Option("--outcome")] = "unknown",
    sessions_dir: Annotated[Path, typer.Option("--sessions-dir")] = Path(
        ".omf/sessions",
    ),
) -> None:
    with cli_errors(SessionExistsError, SessionNotFoundError, SessionParseError):
        summary = finish_session(
            session_id=session_id,
            outcome=_outcome(outcome),
            sessions_dir=sessions_dir,
        )
        emit_json(summary)


def session_materialize(
    session_id: Annotated[str, typer.Argument()],
    sessions_dir: Annotated[Path, typer.Option("--sessions-dir")] = Path(
        ".omf/sessions",
    ),
    evidence_dir: Annotated[Path, typer.Option("--evidence-dir")] = Path(
        ".omf/evidence",
    ),
) -> None:
    with cli_errors(SessionExistsError, SessionNotFoundError, SessionParseError):
        summary = materialize_session(
            session_id=session_id,
            sessions_dir=sessions_dir,
            evidence_dir=evidence_dir,
        )
        emit_json(summary)


def session_suggest_capability(
    session_id: Annotated[str, typer.Argument()],
    sessions_dir: Annotated[Path, typer.Option("--sessions-dir")] = Path(
        ".omf/sessions",
    ),
) -> None:
    with cli_errors(SessionExistsError, SessionNotFoundError, SessionParseError):
        summary = suggest_session_capability(
            session_id=session_id,
            sessions_dir=sessions_dir,
        )
        emit_json(summary)


def _activation_source(value: ActivationSource) -> SessionActivationSource:
    return value


def _event_type(value: EventType) -> AgentSessionEventType:
    return value


def _outcome(value: Outcome) -> TaskOutcome:
    return value


def _risk_categories(
    values: list[str] | None,
) -> tuple[CommandRiskCategory, ...]:
    if not values:
        return ()
    allowed: tuple[RiskCategory, ...] = (
        "write",
        "destructive",
        "external_call",
        "credential_access",
        "production_write",
        "paid_operation",
    )
    invalid = tuple(value for value in values if value not in allowed)
    if invalid:
        expected = ", ".join(allowed)
        message = f"--risk-category must be one of {expected}; got {invalid[0]!r}"
        raise typer.BadParameter(message)
    return tuple(cast("CommandRiskCategory", value) for value in values)


def register(session_app: typer.Typer) -> None:
    session_app.command("start", help="Start an OMF agent session.")(session_start)
    session_app.command("event", help="Record an OMF session event.")(session_event)
    session_app.command("finish", help="Finish an OMF session.")(session_finish)
    session_app.command(
        "materialize",
        help="Convert an OMF session into immutable evidence.",
    )(session_materialize)
    session_app.command(
        "suggest-capability",
        help="Suggest a capability name for an OMF session.",
    )(session_suggest_capability)
