import hashlib
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from pydantic import Field

from oh_my_field.integrity import append_integrity_link, integrity_link
from oh_my_field.models import (
    CAPABILITY_NAME_PATTERN,
    ArtifactIntegrityLink,
    CapabilityManifest,
    CapturedTextFile,
    ContextBundle,
    ContextItem,
    ContextPackPlan,
    ContextSource,
    EvidenceRecord,
    ExcludedContextItem,
    StrictModel,
)
from oh_my_field.storage import load_evidence, load_manifest, write_context_bundle

CONTEXT_NODES: Final = (
    "load_manifest",
    "load_source_evidence",
    "select_context",
    "validate_context",
    "write_context",
    "summarize",
)
SUMMARY_MAX_CHARS: Final = 120

type Clock = Callable[[], datetime]
type TokenFactory = Callable[[], str]


class ContextError(Exception):
    pass


@dataclass
class ContextStateError(ContextError):
    key: str

    def __str__(self) -> str:
        return f"context workflow state missing {self.key!r}"


@dataclass(frozen=True, slots=True)
class ContextDependencies:
    clock: Clock
    token_factory: TokenFactory


class ContextRequest(StrictModel):
    capability_name: str = Field(pattern=CAPABILITY_NAME_PATTERN)
    capabilities_dir: Path
    evidence_dir: Path
    context_dir: Path
    include_optional: bool = False
    query: str | None = None
    max_chars: int | None = Field(default=None, ge=1)


class ContextSummary(StrictModel):
    context_id: str
    context_path: str
    capability_name: str
    required_count: int
    optional_count: int


class ContextState(TypedDict, total=False):
    request: ContextRequest
    dependencies: ContextDependencies
    manifest: CapabilityManifest
    source_evidence: EvidenceRecord
    bundle: ContextBundle
    bundle_path: Path
    summary: ContextSummary


def run_context_workflow(
    request: ContextRequest,
    dependencies: ContextDependencies | None = None,
) -> ContextSummary:
    graph = _build_context_graph()
    initial_state = ContextState(
        request=request,
        dependencies=dependencies or _default_dependencies(),
    )
    final_state = graph.invoke(initial_state)
    return _state_summary(final_state)


def _build_context_graph() -> CompiledStateGraph[
    ContextState,
    None,
    ContextState,
    ContextState,
]:
    builder: StateGraph[ContextState, None, ContextState, ContextState] = StateGraph(
        ContextState,
    )
    builder.add_node("load_manifest", _load_manifest)
    builder.add_node("load_source_evidence", _load_source_evidence)
    builder.add_node("select_context", _select_context)
    builder.add_node("validate_context", _validate_context)
    builder.add_node("write_context", _write_context)
    builder.add_node("summarize", _summarize)
    builder.add_edge(START, "load_manifest")
    builder.add_edge("load_manifest", "load_source_evidence")
    builder.add_edge("load_source_evidence", "select_context")
    builder.add_edge("select_context", "validate_context")
    builder.add_edge("validate_context", "write_context")
    builder.add_edge("write_context", "summarize")
    builder.add_edge("summarize", END)
    return builder.compile()


def _default_dependencies() -> ContextDependencies:
    return ContextDependencies(clock=_now_utc, token_factory=_token_suffix)


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _token_suffix() -> str:
    return secrets.token_hex(4)


def _load_manifest(state: ContextState) -> ContextState:
    request = _state_request(state)
    manifest = load_manifest(request.capability_name, request.capabilities_dir)
    return ContextState(manifest=manifest)


def _load_source_evidence(state: ContextState) -> ContextState:
    request = _state_request(state)
    manifest = _state_manifest(state)
    evidence = load_evidence(manifest.source_evidence_id, request.evidence_dir)
    return ContextState(source_evidence=evidence)


def _select_context(state: ContextState) -> ContextState:
    request = _state_request(state)
    dependencies = _state_dependencies(state)
    manifest = _state_manifest(state)
    evidence = _state_source_evidence(state)
    created_at = dependencies.clock().astimezone(UTC)
    required_paths = set(manifest.context.required)
    optional_paths = set(manifest.context.optional)
    forbidden = manifest.context.forbidden
    field_forbidden = _field_forbidden(manifest)
    all_forbidden = tuple(dict.fromkeys((*forbidden, *field_forbidden)))
    required_context = tuple(
        file
        for file in evidence.files
        if not _is_forbidden(file.path, all_forbidden)
        and (file.path in required_paths or file.role == "context")
    )
    optional_context: tuple[CapturedTextFile, ...] = ()
    if request.include_optional:
        optional_context = tuple(
            file
            for file in evidence.files
            if file.path in optional_paths
            and file not in required_context
            and _matches_query(file, request.query)
            and not _is_forbidden(file.path, all_forbidden)
        )
    selected_context = (*required_context, *optional_context)
    max_chars = _max_chars(request, manifest)
    pack_plan = ContextPackPlan(
        required=tuple(
            _context_item(
                file,
                "required by capability context policy",
                manifest,
                request.query,
                max_chars,
            )
            for file in required_context
        ),
        optional=tuple(
            _context_item(
                file,
                "optional context selected by query",
                manifest,
                request.query,
                max_chars,
            )
            for file in optional_context
        ),
        excluded=tuple(
            _excluded_context_item(
                file,
                forbidden,
                request.query,
                manifest,
                request.include_optional,
            )
            for file in evidence.files
            if file not in selected_context
        ),
        token_estimate=sum(_token_estimate(file.content) for file in selected_context),
        compression_strategy=_compression_strategy(request, manifest),
        source_priority=manifest.context.source_priority,
        recall_notes=_recall_notes(manifest, evidence),
    )
    bundle = ContextBundle(
        id=f"{created_at:%Y%m%dT%H%M%SZ}-{dependencies.token_factory()}",
        created_at=created_at,
        capability_name=manifest.name,
        source_evidence_id=evidence.id,
        required_context=required_context,
        optional_context=optional_context,
        summaries=tuple(_summary_for_file(file) for file in selected_context),
        compressed_context=tuple(
            _compress_file(file, max_chars) for file in selected_context
        ),
        policy=manifest.context,
        pack_plan=pack_plan,
    )
    bundle = bundle.model_copy(
        update={"integrity_chain": (_evidence_integrity_link(evidence),)},
    )
    bundle = append_integrity_link(
        bundle,
        artifact_type="context",
        artifact_id=bundle.id,
        previous_sha256=bundle.integrity_chain[-1].sha256,
    )
    return ContextState(bundle=bundle)


def _validate_context(state: ContextState) -> ContextState:
    bundle = _state_bundle(state)
    checked = ContextBundle.model_validate(bundle)
    return ContextState(bundle=checked)


def _write_context(state: ContextState) -> ContextState:
    request = _state_request(state)
    bundle = _state_bundle(state)
    bundle_path = write_context_bundle(bundle, request.context_dir)
    return ContextState(bundle_path=bundle_path)


def _summarize(state: ContextState) -> ContextState:
    bundle = _state_bundle(state)
    bundle_path = _state_bundle_path(state)
    summary = ContextSummary(
        context_id=bundle.id,
        context_path=str(bundle_path),
        capability_name=bundle.capability_name,
        required_count=len(bundle.required_context),
        optional_count=len(bundle.optional_context),
    )
    return ContextState(summary=summary)


def _matches_query(file: CapturedTextFile, query: str | None) -> bool:
    if query is None:
        return True
    needle = query.casefold()
    return needle in file.path.casefold() or needle in file.content.casefold()


def _is_forbidden(path: str, forbidden: tuple[str, ...]) -> bool:
    return any(rule in path for rule in forbidden)


def _field_forbidden(manifest: CapabilityManifest) -> tuple[str, ...]:
    if manifest.field is None:
        return ()
    return manifest.field.policies.forbidden_context


def _context_item(
    file: CapturedTextFile,
    reason: str,
    manifest: CapabilityManifest,
    query: str | None,
    max_chars: int | None,
) -> ContextItem:
    source = _source_for_file(file, manifest)
    return ContextItem(
        path=file.path,
        source=source.name,
        reason=reason,
        token_estimate=_token_estimate(file.content),
        source_type=source.type,
        freshness=source.freshness,
        priority=source.priority,
        matched_query=query is not None and _matches_query(file, query),
        compressed=max_chars is not None and len(file.content) > max_chars,
    )


def _excluded_context_item(
    file: CapturedTextFile,
    forbidden: tuple[str, ...],
    query: str | None,
    manifest: CapabilityManifest,
    include_optional: bool,
) -> ExcludedContextItem:
    source = _source_for_file(file, manifest)
    reason = "not selected by capability context policy"
    if _is_forbidden(file.path, forbidden):
        reason = "forbidden by capability context policy"
    elif _is_forbidden(file.path, _field_forbidden(manifest)):
        reason = "forbidden by field policy"
    elif file.path in manifest.context.optional and not include_optional:
        reason = "optional context was not requested"
    elif query is not None and not _matches_query(file, query):
        reason = "optional context did not match query"
    return ExcludedContextItem(
        path=file.path,
        source=source.name,
        reason=reason,
        source_type=source.type,
        freshness=source.freshness,
        priority=source.priority,
    )


def _source_for_file(
    file: CapturedTextFile,
    manifest: CapabilityManifest,
) -> ContextSource:
    for source in manifest.context.sources:
        if file.path in _source_locations(source):
            return source
    for source in manifest.context.sources:
        if source.type == "evidence":
            return source
    return ContextSource(
        name="source_evidence",
        type="evidence",
        location=manifest.source_evidence_id,
        freshness="captured",
        priority=100,
    )


def _source_locations(source: ContextSource) -> tuple[str, ...]:
    return tuple(item.strip() for item in source.location.split(",") if item.strip())


def _recall_notes(
    manifest: CapabilityManifest,
    evidence: EvidenceRecord,
) -> tuple[str, ...]:
    notes: list[str] = []
    if manifest.context.evidence_recall_strategy is not None:
        notes.append(f"evidence_recall: {manifest.context.evidence_recall_strategy}")
    if manifest.field is not None and manifest.field.failure_history.recall_strategy:
        notes.append(f"field_recall: {manifest.field.failure_history.recall_strategy}")
    notes.extend(f"source_failure: {failure}" for failure in evidence.harness.failures)
    notes.extend(f"source_error: {error}" for error in evidence.errors)
    return tuple(notes)


def _token_estimate(content: str) -> int:
    return max(1, len(content) // 4) if content else 0


def _compression_strategy(
    request: ContextRequest,
    manifest: CapabilityManifest,
) -> str:
    if request.max_chars is not None:
        return f"truncate_each_item_to_{request.max_chars}_chars"
    if manifest.context.compression_rule is not None:
        return manifest.context.compression_rule
    if manifest.context.maximum_token_budget is not None:
        return f"fit_to_{manifest.context.maximum_token_budget}_tokens"
    return "none"


def _evidence_integrity_link(evidence: EvidenceRecord) -> ArtifactIntegrityLink:
    if evidence.integrity_chain:
        return evidence.integrity_chain[-1]
    return integrity_link(
        artifact_type="evidence",
        artifact_id=evidence.id,
        model=evidence,
    )


def _summary_for_file(file: CapturedTextFile) -> str:
    text = " ".join(file.content.split())
    if len(text) > SUMMARY_MAX_CHARS:
        text = f"{text[: SUMMARY_MAX_CHARS - 3]}..."
    return f"{file.path}: {text}"


def _compress_file(file: CapturedTextFile, max_chars: int | None) -> CapturedTextFile:
    if max_chars is None or len(file.content) <= max_chars:
        return file
    content = file.content[:max_chars]
    raw_content = content.encode("utf-8")
    return file.model_copy(
        update={
            "content": content,
            "size_bytes": len(raw_content),
            "sha256": hashlib.sha256(raw_content).hexdigest(),
        },
    )


def _max_chars(request: ContextRequest, manifest: CapabilityManifest) -> int | None:
    if request.max_chars is not None:
        return request.max_chars
    if manifest.context.maximum_token_budget is None:
        return None
    return manifest.context.maximum_token_budget * 4


def _state_request(state: ContextState) -> ContextRequest:
    request = state.get("request")
    if request is None:
        raise ContextStateError(key="request")
    return request


def _state_dependencies(state: ContextState) -> ContextDependencies:
    dependencies = state.get("dependencies")
    if dependencies is None:
        raise ContextStateError(key="dependencies")
    return dependencies


def _state_manifest(state: ContextState) -> CapabilityManifest:
    manifest = state.get("manifest")
    if manifest is None:
        raise ContextStateError(key="manifest")
    return manifest


def _state_source_evidence(state: ContextState) -> EvidenceRecord:
    evidence = state.get("source_evidence")
    if evidence is None:
        raise ContextStateError(key="source_evidence")
    return evidence


def _state_bundle(state: ContextState) -> ContextBundle:
    bundle = state.get("bundle")
    if bundle is None:
        raise ContextStateError(key="bundle")
    return bundle


def _state_bundle_path(state: ContextState) -> Path:
    bundle_path = state.get("bundle_path")
    if bundle_path is None:
        raise ContextStateError(key="bundle_path")
    return bundle_path


def _state_summary(state: ContextState) -> ContextSummary:
    summary = state.get("summary")
    if summary is None:
        raise ContextStateError(key="summary")
    return summary
