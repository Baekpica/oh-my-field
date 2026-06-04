import re
from datetime import UTC, datetime
from pathlib import Path

from oh_my_field.application.portability.ids import new_id
from oh_my_field.domain.models import (
    CommandExecution,
    CommandRiskCategory,
    EvidenceRecord,
    HarnessResult,
    RuntimeInfo,
    SuccessLabel,
    TaskOutcome,
)
from oh_my_field.domain.session.models import (
    AgentSession,
    AgentSessionEvent,
    AgentSessionEventType,
    AgentSessionStatus,
    SessionActivationSource,
    SessionEventSummary,
    SessionFinishSummary,
    SessionMaterializeSummary,
    SessionStartSummary,
    SessionSuggestSummary,
)
from oh_my_field.infrastructure.fs.storage import write_evidence
from oh_my_field.infrastructure.session.store import load_session, write_session
from oh_my_field.integrity import append_integrity_link


def start_session(  # noqa: PLR0913
    *,
    runtime: str,
    model: str | None,
    project_root: Path,
    activation_source: SessionActivationSource,
    goal: str,
    sessions_dir: Path,
) -> SessionStartSummary:
    created_at = datetime.now(UTC)
    session_id = new_id(created_at)
    goal_event = AgentSessionEvent(
        id=new_id(created_at),
        created_at=created_at,
        type="goal",
        summary=goal,
    )
    session = AgentSession(
        id=session_id,
        created_at=created_at,
        updated_at=created_at,
        runtime=runtime,
        model=model,
        project_root=str(project_root),
        activation_source=activation_source,
        goal=goal,
        events=(goal_event,),
    )
    path = write_session(session, sessions_dir, overwrite=False)
    return SessionStartSummary(
        session_id=session.id,
        session_path=str(path),
        status=session.status,
        next_action="record session events, then finish and materialize evidence",
    )


def record_session_event(  # noqa: PLR0913
    *,
    session_id: str,
    event_type: AgentSessionEventType,
    summary: str,
    sessions_dir: Path,
    path: str | None = None,
    command: str | None = None,
    exit_code: int | None = None,
    risk_categories: tuple[CommandRiskCategory, ...] = (),
) -> SessionEventSummary:
    session = load_session(session_id, sessions_dir)
    created_at = datetime.now(UTC)
    event = AgentSessionEvent(
        id=new_id(created_at),
        created_at=created_at,
        type=event_type,
        summary=summary,
        path=path,
        command=command,
        exit_code=exit_code,
        risk_categories=risk_categories,
    )
    updated = session.model_copy(
        update={
            "updated_at": created_at,
            "events": (*session.events, event),
        },
    )
    written = write_session(updated, sessions_dir, overwrite=True)
    return SessionEventSummary(
        session_id=session_id,
        event_id=event.id,
        event_count=len(updated.events),
        session_path=str(written),
    )


def finish_session(
    *,
    session_id: str,
    outcome: TaskOutcome,
    sessions_dir: Path,
) -> SessionFinishSummary:
    session = load_session(session_id, sessions_dir)
    created_at = datetime.now(UTC)
    status = _status_for_outcome(outcome)
    completion = AgentSessionEvent(
        id=new_id(created_at),
        created_at=created_at,
        type="completion",
        summary=f"session finished with outcome {outcome}",
    )
    updated = session.model_copy(
        update={
            "updated_at": created_at,
            "status": status,
            "outcome": outcome,
            "events": (*session.events, completion),
        },
    )
    written = write_session(updated, sessions_dir, overwrite=True)
    return SessionFinishSummary(
        session_id=session_id,
        status=status,
        outcome=outcome,
        session_path=str(written),
        next_action="materialize the session into immutable evidence",
    )


def materialize_session(
    *,
    session_id: str,
    sessions_dir: Path,
    evidence_dir: Path,
) -> SessionMaterializeSummary:
    session = load_session(session_id, sessions_dir)
    created_at = datetime.now(UTC)
    evidence = _evidence_from_session(
        session=session,
        created_at=created_at,
        evidence_id=new_id(created_at),
    )
    evidence = append_integrity_link(
        evidence,
        artifact_type="evidence",
        artifact_id=evidence.id,
    )
    evidence_path = write_evidence(evidence, evidence_dir)
    updated = session.model_copy(
        update={
            "updated_at": created_at,
            "evidence_ids": (*session.evidence_ids, evidence.id),
        },
    )
    written = write_session(updated, sessions_dir, overwrite=True)
    return SessionMaterializeSummary(
        session_id=session_id,
        evidence_id=evidence.id,
        evidence_path=str(evidence_path),
        session_path=str(written),
        next_action="promote the evidence if this workflow should become reusable",
    )


def suggest_session_capability(
    *,
    session_id: str,
    sessions_dir: Path,
) -> SessionSuggestSummary:
    session = load_session(session_id, sessions_dir)
    suggestion = _capability_name(session.goal)
    updated = session.model_copy(
        update={"suggested_capabilities": (suggestion,)},
    )
    written = write_session(updated, sessions_dir, overwrite=True)
    return SessionSuggestSummary(
        session_id=session_id,
        suggested_capabilities=updated.suggested_capabilities,
        session_path=str(written),
    )


def _status_for_outcome(outcome: TaskOutcome) -> AgentSessionStatus:
    if outcome == "failure":
        return "failed"
    return "completed"


def _evidence_from_session(
    *,
    session: AgentSession,
    created_at: datetime,
    evidence_id: str,
) -> EvidenceRecord:
    commands = tuple(
        event.command
        for event in session.events
        if event.type == "command" and event.command is not None
    )
    command_executions = tuple(
        CommandExecution(
            command=event.command,
            cwd=session.project_root,
            exit_code=event.exit_code,
            duration_ms=0,
            risk_categories=event.risk_categories,
        )
        for event in session.events
        if event.type == "command"
        and event.command is not None
        and event.exit_code is not None
    )
    feedback = tuple(
        event.summary for event in session.events if event.type == "user_feedback"
    )
    context = tuple(
        event.path or event.summary
        for event in session.events
        if event.type == "context"
    )
    artifacts = tuple(
        event.path or event.summary
        for event in session.events
        if event.type in ("artifact", "diff", "test_result")
    )
    failures = tuple(
        event.summary
        for event in session.events
        if event.type == "test_result" and event.exit_code not in (None, 0)
    )
    outcome = session.outcome
    success_label = _success_label(outcome)
    harness_status = "fail" if outcome == "failure" or failures else "pass"
    return EvidenceRecord(
        id=evidence_id,
        session_id=session.id,
        created_at=created_at,
        goal=session.goal,
        normalized_goal=session.goal,
        field=Path(session.project_root).name or "agent_session",
        runtime=RuntimeInfo(name=session.runtime, model=session.model),
        input_context=context,
        generated_commands=commands,
        command_executions=command_executions,
        errors=failures,
        feedback=feedback,
        final_artifacts=artifacts,
        harness=HarnessResult(
            status=harness_status,
            checks=tuple(
                event.summary for event in session.events if event.type == "test_result"
            ),
            failures=failures,
            required_checks=(),
            human_review_required=True,
        ),
        capture_status="captured",
        task_outcome=outcome,
        success_or_failure_label=success_label,
        improvement_notes=("materialized from OMF agent session",),
    )


def _success_label(outcome: TaskOutcome) -> SuccessLabel:
    if outcome == "success":
        return "success"
    if outcome == "failure":
        return "failure"
    return "unknown"


def _capability_name(goal: str) -> str:
    slug = re.sub(r"[^a-z0-9_]+", "_", goal.casefold()).strip("_")
    slug = re.sub(r"_+", "_", slug)
    if not slug:
        return "agent_session_capability"
    if not slug[0].isalpha():
        slug = f"capability_{slug}"
    return slug[:64].rstrip("_") or "agent_session_capability"
