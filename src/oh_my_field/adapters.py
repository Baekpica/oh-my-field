import hashlib
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from pydantic import Field

from oh_my_field.integrity import append_integrity_link
from oh_my_field.models import (
    AgentImporterName,
    AgentImporterSpec,
    AgentRunSource,
    CapturedFileRole,
    CapturedTextFile,
    EvidenceRecord,
    HarnessResult,
    LatencyMetrics,
    RuntimeInfo,
    StrictModel,
    ToolCallRecord,
)
from oh_my_field.storage import write_evidence

type Clock = Callable[[], datetime]
type TokenFactory = Callable[[], str]

IMPORTER_SPECS: tuple[AgentImporterSpec, ...] = (
    AgentImporterSpec(
        name="codex",
        display_name="Codex",
        captures=("run log", "diff", "test result", "command output", "artifact"),
        replays=("capability eval",),
        artifact_roles=("artifact", "diff", "test_result"),
    ),
    AgentImporterSpec(
        name="claude_code",
        display_name="Claude Code",
        captures=("run log", "diff", "test result", "command output", "artifact"),
        replays=("capability eval",),
        artifact_roles=("artifact", "diff", "test_result"),
    ),
    AgentImporterSpec(
        name="hermes",
        display_name="Hermes",
        captures=("run log", "diff", "test result", "command output", "artifact"),
        replays=("capability eval",),
        artifact_roles=("artifact", "diff", "test_result"),
    ),
)
ADAPTER_SPECS = IMPORTER_SPECS


class ImporterError(Exception):
    pass


class AdapterError(ImporterError):
    pass


@dataclass
class AgentArtifactReadError(AdapterError):
    path: Path
    reason: str

    def __str__(self) -> str:
        return f"could not read agent artifact {self.path}: {self.reason}"


@dataclass(frozen=True, slots=True)
class AgentImportDependencies:
    clock: Clock
    token_factory: TokenFactory


class AgentArtifactInput(StrictModel):
    role: CapturedFileRole
    path: Path


class AgentImportRequest(StrictModel):
    adapter: AgentImporterName
    log_path: Path
    goal: str = Field(min_length=1)
    field: str = Field(min_length=1)
    model: str | None = None
    evidence_dir: Path
    artifacts: tuple[AgentArtifactInput, ...] = ()
    artifact_roots: tuple[Path, ...] = ()


class AgentImportSummary(StrictModel):
    evidence_id: str
    evidence_path: str
    adapter: AgentImporterName
    artifact_count: int


def import_agent_run(
    request: AgentImportRequest,
    dependencies: AgentImportDependencies | None = None,
) -> AgentImportSummary:
    dependencies = dependencies or _default_dependencies()
    created_at = dependencies.clock().astimezone(UTC)
    evidence_id = f"{created_at:%Y%m%dT%H%M%SZ}-{dependencies.token_factory()}"
    importer = request.adapter
    artifact_inputs = _dedupe_artifacts(
        (
            AgentArtifactInput(role="artifact", path=request.log_path),
            *request.artifacts,
            *_discover_artifacts(request.artifact_roots, request.log_path),
        ),
    )
    files = tuple(_read_artifact(artifact) for artifact in artifact_inputs)
    evidence = EvidenceRecord(
        id=evidence_id,
        session_id=evidence_id,
        created_at=created_at,
        goal=request.goal,
        normalized_goal=_normalize_goal(request.goal),
        field=request.field,
        runtime=RuntimeInfo(
            name=importer,
            model=request.model,
            tools=("external_agent_log", f"importer:{importer}"),
        ),
        input_context=tuple(file.path for file in files if file.role == "artifact"),
        files=files,
        final_artifacts=tuple(file.path for file in files),
        harness=HarnessResult(
            status="pass",
            checks=("agent_log_imported", "artifacts_readable"),
            required_checks=("agent_log_imported", "artifacts_readable"),
        ),
        latency_metrics=LatencyMetrics(),
        success_or_failure_label="unknown",
    )
    evidence = evidence.model_copy(
        update={
            "tool_calls": (
                ToolCallRecord(
                    tool="agent_importer.import_run",
                    input=AgentRunSource(
                        importer=importer,
                        path=str(request.log_path),
                    ).model_dump_json(),
                    output=f"captured {len(files)} artifacts",
                ),
            ),
        },
    )
    evidence = append_integrity_link(
        evidence,
        artifact_type="evidence",
        artifact_id=evidence.id,
    )
    evidence_path = write_evidence(evidence, request.evidence_dir)
    return AgentImportSummary(
        evidence_id=evidence.id,
        evidence_path=str(evidence_path),
        adapter=importer,
        artifact_count=len(files),
    )


def _default_dependencies() -> AgentImportDependencies:
    return AgentImportDependencies(clock=_now_utc, token_factory=_token_suffix)


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _token_suffix() -> str:
    return secrets.token_hex(4)


def _read_artifact(artifact: AgentArtifactInput) -> CapturedTextFile:
    try:
        content = artifact.path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise AgentArtifactReadError(path=artifact.path, reason=str(exc)) from exc
    raw_content = content.encode("utf-8")
    return CapturedTextFile(
        role=artifact.role,
        path=str(artifact.path),
        content=content,
        size_bytes=len(raw_content),
        sha256=hashlib.sha256(raw_content).hexdigest(),
    )


def _discover_artifacts(
    roots: tuple[Path, ...],
    log_path: Path,
) -> tuple[AgentArtifactInput, ...]:
    discovered: list[AgentArtifactInput] = []
    for root in roots:
        paths = (root,) if root.is_file() else tuple(sorted(root.rglob("*")))
        discovered.extend(
            AgentArtifactInput(role=_infer_artifact_role(path), path=path)
            for path in paths
            if path.is_file() and path != log_path
        )
    return tuple(discovered)


def _infer_artifact_role(path: Path) -> CapturedFileRole:
    name = path.name.casefold()
    suffix = path.suffix.casefold()
    if suffix in {".diff", ".patch"}:
        return "diff"
    if "pytest" in name or "test" in name or "junit" in name or "coverage" in name:
        return "test_result"
    if "stdout" in name or "stderr" in name or "output" in name or suffix == ".log":
        return "command_output"
    if "tool" in name:
        return "tool_call"
    return "artifact"


def _dedupe_artifacts(
    artifacts: tuple[AgentArtifactInput, ...],
) -> tuple[AgentArtifactInput, ...]:
    deduped: dict[Path, AgentArtifactInput] = {}
    for artifact in artifacts:
        deduped.setdefault(artifact.path, artifact)
    return tuple(deduped.values())


def _normalize_goal(goal: str) -> str:
    return " ".join(goal.casefold().split())
