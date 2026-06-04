import fnmatch
import hashlib
import mimetypes
import re
import secrets
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib import metadata
from pathlib import Path
from typing import Final, Protocol, cast

from pydantic import Field

from oh_my_field.domain.models import (
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
    TaskOutcome,
    ToolCallRecord,
)
from oh_my_field.domain.runtime.adapter import RuntimeAdapter
from oh_my_field.domain.runtime.registry import AdapterRegistry
from oh_my_field.infrastructure.fs.hashing import append_integrity_link
from oh_my_field.infrastructure.fs.storage import write_evidence

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
OMFIGNORE_FILE_NAME: Final = ".omfignore"
DEFAULT_EXCLUDE_PATTERNS: Final = (
    ".git/**",
    ".venv/**",
    "node_modules/**",
    "dist/**",
    "build/**",
    ".env*",
    "*.pem",
    "*.key",
    "*.sqlite",
    "*.db",
    "*.zip",
    "*.tar.gz",
)
RUNTIME_ADAPTER_ENTRY_POINT_GROUP: Final = "oh_my_field.runtime_adapters"


class RuntimeAdapterEntryPoint(Protocol):
    @property
    def name(self) -> str: ...

    def load(self) -> object: ...


class ImporterError(Exception):
    pass


class AdapterError(ImporterError):
    pass


@dataclass
class RuntimeAdapterPluginError(AdapterError):
    source: str
    reason: str

    def __str__(self) -> str:
        return f"could not load runtime adapter plugin {self.source!r}: {self.reason}"


@dataclass
class AgentArtifactReadError(AdapterError):
    path: Path
    reason: str

    def __str__(self) -> str:
        return f"could not read agent artifact {self.path}: {self.reason}"


@dataclass
class AgentArtifactLimitError(AdapterError):
    reason: str

    def __str__(self) -> str:
        return self.reason


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
    max_artifact_bytes: int | None = Field(default=None, ge=1)
    max_artifact_count: int | None = Field(default=None, ge=1)
    max_total_artifact_bytes: int | None = Field(default=None, ge=1)
    exclude_patterns: tuple[str, ...] = ()
    redact_secrets: bool = False
    task_outcome: TaskOutcome = "unknown"


class AgentImportSummary(StrictModel):
    evidence_id: str
    evidence_path: str
    adapter: AgentImporterName
    artifact_count: int


class ImporterAdapter:
    """Generic runtime adapter that imports a run without runtime-specific parsing.

    Every built-in runtime shares this importer today; a runtime that needs its
    own log parsing implements the RuntimeAdapter protocol and registers itself.
    """

    def __init__(self, spec: AgentImporterSpec) -> None:
        """Bind the adapter to its runtime importer spec."""
        self.spec = spec

    def import_run(
        self,
        request: AgentImportRequest,
        dependencies: AgentImportDependencies | None = None,
    ) -> AgentImportSummary:
        return _run_agent_import(request, dependencies)


BUILTIN_ADAPTERS = AdapterRegistry()
for _spec in IMPORTER_SPECS:
    BUILTIN_ADAPTERS.register(_spec.name, ImporterAdapter(_spec))


def builtin_adapter_registry() -> AdapterRegistry:
    registry = AdapterRegistry()
    for spec in IMPORTER_SPECS:
        register_runtime_adapter(registry, ImporterAdapter(spec))
    return registry


def register_runtime_adapter(
    registry: AdapterRegistry,
    adapter: RuntimeAdapter,
) -> None:
    registry.register(adapter.spec.name, adapter)


def build_adapter_registry(
    *,
    include_plugins: bool = True,
    entry_points: Iterable[RuntimeAdapterEntryPoint] | None = None,
) -> AdapterRegistry:
    registry = builtin_adapter_registry()
    if include_plugins:
        load_runtime_adapter_plugins(registry, entry_points=entry_points)
    return registry


def load_runtime_adapter_plugins(
    registry: AdapterRegistry,
    *,
    entry_points: Iterable[RuntimeAdapterEntryPoint] | None = None,
) -> None:
    selected = _runtime_adapter_entry_points() if entry_points is None else entry_points
    for entry_point in selected:
        try:
            adapter = _runtime_adapter_candidate(entry_point.load())
            register_runtime_adapter(registry, adapter)
        except Exception as exc:
            raise RuntimeAdapterPluginError(
                source=entry_point.name,
                reason=str(exc),
            ) from exc


def _runtime_adapter_candidate(candidate: object) -> RuntimeAdapter:
    if _looks_like_runtime_adapter(candidate):
        return cast("RuntimeAdapter", candidate)
    if callable(candidate):
        adapter = cast("Callable[[], object]", candidate)()
        if _looks_like_runtime_adapter(adapter):
            return cast("RuntimeAdapter", adapter)
    message = "entry point must load a RuntimeAdapter or zero-argument factory"
    raise TypeError(message)


def _looks_like_runtime_adapter(candidate: object) -> bool:
    return hasattr(candidate, "spec") and hasattr(candidate, "import_run")


def _runtime_adapter_entry_points() -> tuple[RuntimeAdapterEntryPoint, ...]:
    selected = metadata.entry_points(group=RUNTIME_ADAPTER_ENTRY_POINT_GROUP)
    return tuple(cast("Iterable[RuntimeAdapterEntryPoint]", selected))


def import_agent_run(
    request: AgentImportRequest,
    dependencies: AgentImportDependencies | None = None,
) -> AgentImportSummary:
    """Import an external agent run through its registered runtime adapter."""
    return build_adapter_registry().get(request.adapter).import_run(
        request,
        dependencies,
    )


def _run_agent_import(
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
            *_discover_artifacts(
                request.artifact_roots,
                request.log_path,
                exclude_patterns=request.exclude_patterns,
                max_artifact_count=request.max_artifact_count,
                max_total_artifact_bytes=request.max_total_artifact_bytes,
            ),
        ),
    )
    files = tuple(
        _read_artifact(
            artifact,
            max_bytes=request.max_artifact_bytes,
            redact_secrets=request.redact_secrets,
        )
        for artifact in artifact_inputs
    )
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
        capture_status="captured",
        task_outcome=request.task_outcome,
        success_or_failure_label=request.task_outcome,
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


def _read_artifact(
    artifact: AgentArtifactInput,
    *,
    max_bytes: int | None,
    redact_secrets: bool,
) -> CapturedTextFile:
    try:
        raw = artifact.path.read_bytes()
    except OSError as exc:
        raise AgentArtifactReadError(path=artifact.path, reason=str(exc)) from exc
    sha256 = hashlib.sha256(raw).hexdigest()
    size_bytes = len(raw)
    mime_type, _ = mimetypes.guess_type(str(artifact.path))
    too_large = max_bytes is not None and size_bytes > max_bytes
    text = None if too_large else _decode_utf8(raw)
    if text is None:
        # Binary or oversized: record metadata only, keep content external.
        return CapturedTextFile(
            role=artifact.role,
            path=str(artifact.path),
            content="",
            size_bytes=size_bytes,
            sha256=sha256,
            mime_type=mime_type,
            storage_mode="external",
        )
    redacted = False
    if redact_secrets:
        text, redacted = _redact_secrets(text)
    return CapturedTextFile(
        role=artifact.role,
        path=str(artifact.path),
        content=text,
        size_bytes=size_bytes,
        sha256=sha256,
        mime_type=mime_type,
        storage_mode="inline",
        redacted=redacted,
    )


def _decode_utf8(raw: bytes) -> str | None:
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return None


_SECRET_KEY_VALUE: Final = re.compile(
    r"(?i)(\b(?:api[_-]?key|secret|token|password|passwd|pwd)\b\s*[:=]\s*)(\S+)",
)
_AWS_ACCESS_KEY: Final = re.compile(r"\bAKIA[0-9A-Z]{16}\b")
_BEARER_TOKEN: Final = re.compile(r"(?i)(bearer\s+)\S+")
_REDACTED: Final = "[REDACTED]"


def _redact_secrets(text: str) -> tuple[str, bool]:
    redacted, key_value = _SECRET_KEY_VALUE.subn(rf"\1{_REDACTED}", text)
    redacted, aws = _AWS_ACCESS_KEY.subn(_REDACTED, redacted)
    redacted, bearer = _BEARER_TOKEN.subn(rf"\1{_REDACTED}", redacted)
    return redacted, bool(key_value + aws + bearer)


def _discover_artifacts(
    roots: tuple[Path, ...],
    log_path: Path,
    *,
    exclude_patterns: tuple[str, ...] = (),
    max_artifact_count: int | None = None,
    max_total_artifact_bytes: int | None = None,
) -> tuple[AgentArtifactInput, ...]:
    discovered: list[AgentArtifactInput] = []
    for root in roots:
        root_patterns = _root_exclude_patterns(root, exclude_patterns)
        paths = (root,) if root.is_file() else tuple(sorted(root.rglob("*")))
        for path in paths:
            if (
                not path.is_file()
                or path == log_path
                or path.is_symlink()
                or _is_excluded(path, root=root, patterns=root_patterns)
            ):
                continue
            discovered.append(
                AgentArtifactInput(role=_infer_artifact_role(path), path=path),
            )
            _enforce_artifact_limits(
                discovered,
                max_artifact_count=max_artifact_count,
                max_total_artifact_bytes=max_total_artifact_bytes,
            )
    return tuple(discovered)


def _root_exclude_patterns(
    root: Path,
    exclude_patterns: tuple[str, ...],
) -> tuple[str, ...]:
    omfignore = root / OMFIGNORE_FILE_NAME if root.is_dir() else None
    return (
        *DEFAULT_EXCLUDE_PATTERNS,
        *((OMFIGNORE_FILE_NAME,) if root.is_dir() else ()),
        *_read_omfignore_patterns(omfignore),
        *exclude_patterns,
    )


def _read_omfignore_patterns(path: Path | None) -> tuple[str, ...]:
    if path is None or not path.exists():
        return ()
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise AgentArtifactReadError(path=path, reason=str(exc)) from exc
    return tuple(
        line.strip()
        for line in lines
        if line.strip() and not line.lstrip().startswith("#")
    )


def _is_excluded(path: Path, *, root: Path, patterns: tuple[str, ...]) -> bool:
    relative = _relative_posix(path, root)
    return any(
        _matches_exclude_pattern(relative, path.name, pattern) for pattern in patterns
    )


def _relative_posix(path: Path, root: Path) -> str:
    if root.is_file():
        return path.name
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.name


def _matches_exclude_pattern(relative: str, name: str, pattern: str) -> bool:
    normalized = pattern.strip().rstrip("/")
    if not normalized:
        return False
    if pattern.endswith("/"):
        return relative == normalized or relative.startswith(f"{normalized}/")
    if normalized.endswith("/**"):
        prefix = normalized.removesuffix("/**")
        return relative == prefix or relative.startswith(f"{prefix}/")
    return fnmatch.fnmatch(relative, normalized) or fnmatch.fnmatch(name, normalized)


def _enforce_artifact_limits(
    artifacts: list[AgentArtifactInput],
    *,
    max_artifact_count: int | None,
    max_total_artifact_bytes: int | None,
) -> None:
    if max_artifact_count is not None and len(artifacts) > max_artifact_count:
        raise AgentArtifactLimitError(
            reason=(
                f"max artifact count exceeded: {len(artifacts)} > {max_artifact_count}"
            ),
        )
    if max_total_artifact_bytes is None:
        return
    total_bytes = sum(artifact.path.stat().st_size for artifact in artifacts)
    if total_bytes > max_total_artifact_bytes:
        raise AgentArtifactLimitError(
            reason=(
                f"max total artifact bytes exceeded: {total_bytes} > "
                f"{max_total_artifact_bytes}"
            ),
        )


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
