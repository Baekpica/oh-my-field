import os
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import yaml
from pydantic import ValidationError

from oh_my_field.models import (
    CapabilityManifest,
    ContextBundle,
    EvalResult,
    EvidenceRecord,
    HumanReviewRecord,
    LearningExport,
    ReflectionReport,
    ReplayRecord,
    WorkflowRunRecord,
)

type YamlValue = (
    str | int | float | bool | None | list["YamlValue"] | dict[str, "YamlValue"]
)


class StorageError(Exception):
    pass


@dataclass
class DuplicateWriteError(StorageError):
    path: Path

    def __str__(self) -> str:
        return f"refusing to overwrite existing file: {self.path}"


@dataclass
class EvidenceNotFoundError(StorageError):
    evidence_id: str
    evidence_dir: Path

    def __str__(self) -> str:
        return f"evidence {self.evidence_id!r} not found in {self.evidence_dir}"


@dataclass
class EvidenceParseError(StorageError):
    path: Path
    reason: str

    def __str__(self) -> str:
        return f"could not parse evidence file {self.path}: {self.reason}"


@dataclass
class ManifestNotFoundError(StorageError):
    capability_name: str
    capabilities_dir: Path

    def __str__(self) -> str:
        return (
            f"manifest for capability {self.capability_name!r} not found in "
            f"{self.capabilities_dir}"
        )


@dataclass
class ManifestParseError(StorageError):
    path: Path
    reason: str

    def __str__(self) -> str:
        return f"could not parse manifest file {self.path}: {self.reason}"


@dataclass
class ReplayNotFoundError(StorageError):
    replay_id: str
    replay_dir: Path

    def __str__(self) -> str:
        return f"replay {self.replay_id!r} not found in {self.replay_dir}"


@dataclass
class ReplayParseError(StorageError):
    path: Path
    reason: str

    def __str__(self) -> str:
        return f"could not parse replay file {self.path}: {self.reason}"


@dataclass
class EvalParseError(StorageError):
    path: Path
    reason: str

    def __str__(self) -> str:
        return f"could not parse eval file {self.path}: {self.reason}"


@dataclass
class EvalNotFoundError(StorageError):
    eval_id: str
    eval_dir: Path

    def __str__(self) -> str:
        return f"eval {self.eval_id!r} not found in {self.eval_dir}"


@dataclass
class WorkflowRunNotFoundError(StorageError):
    run_id: str
    workflow_dir: Path

    def __str__(self) -> str:
        return f"workflow run {self.run_id!r} not found in {self.workflow_dir}"


@dataclass
class WorkflowRunParseError(StorageError):
    path: Path
    reason: str

    def __str__(self) -> str:
        return f"could not parse workflow run file {self.path}: {self.reason}"


def write_evidence(record: EvidenceRecord, evidence_dir: Path) -> Path:
    target_path = evidence_dir / f"{record.id}.json"
    _write_text_exclusive(target_path, record.model_dump_json(indent=2) + "\n")
    return target_path


def write_manifest(manifest: CapabilityManifest, capabilities_dir: Path) -> Path:
    target_path = capabilities_dir / manifest.name / "manifest.yaml"
    _write_text_exclusive(target_path, _manifest_yaml(manifest))
    return target_path


def load_manifest(capability_name: str, capabilities_dir: Path) -> CapabilityManifest:
    manifest_path = capabilities_dir / capability_name / "manifest.yaml"
    if not manifest_path.exists():
        raise ManifestNotFoundError(
            capability_name=capability_name,
            capabilities_dir=capabilities_dir,
        )
    return _load_manifest_path(manifest_path)


def list_manifests(
    capabilities_dir: Path,
) -> tuple[tuple[Path, CapabilityManifest], ...]:
    if not capabilities_dir.exists():
        return ()
    manifest_paths = sorted(capabilities_dir.glob("*/manifest.yaml"))
    return tuple((path, _load_manifest_path(path)) for path in manifest_paths)


def _load_manifest_path(manifest_path: Path) -> CapabilityManifest:
    try:
        raw_yaml = manifest_path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        capability_name = manifest_path.parent.name
        raise ManifestNotFoundError(
            capability_name=capability_name,
            capabilities_dir=manifest_path.parent.parent,
        ) from exc
    except UnicodeDecodeError as exc:
        raise ManifestParseError(path=manifest_path, reason=str(exc)) from exc
    try:
        parsed_yaml = yaml.safe_load(raw_yaml)
    except yaml.YAMLError as exc:
        raise ManifestParseError(path=manifest_path, reason=str(exc)) from exc
    if not isinstance(parsed_yaml, dict):
        raise ManifestParseError(
            path=manifest_path,
            reason=f"expected mapping at top level, got {type(parsed_yaml).__name__}",
        )
    try:
        return CapabilityManifest.model_validate(parsed_yaml)
    except ValidationError as exc:
        raise ManifestParseError(path=manifest_path, reason=str(exc)) from exc


def load_evidence(evidence_id: str, evidence_dir: Path) -> EvidenceRecord:
    evidence_path = evidence_dir / f"{evidence_id}.json"
    if not evidence_path.exists():
        raise EvidenceNotFoundError(evidence_id=evidence_id, evidence_dir=evidence_dir)
    try:
        raw_json = evidence_path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise EvidenceNotFoundError(
            evidence_id=evidence_id,
            evidence_dir=evidence_dir,
        ) from exc
    except UnicodeDecodeError as exc:
        raise EvidenceParseError(path=evidence_path, reason=str(exc)) from exc
    try:
        return EvidenceRecord.model_validate_json(raw_json)
    except ValidationError as exc:
        raise EvidenceParseError(path=evidence_path, reason=str(exc)) from exc


def write_replay(record: ReplayRecord, replay_dir: Path) -> Path:
    target_path = replay_dir / f"{record.id}.json"
    _write_text_exclusive(target_path, record.model_dump_json(indent=2) + "\n")
    return target_path


def load_replay(replay_id: str, replay_dir: Path) -> ReplayRecord:
    replay_path = replay_dir / f"{replay_id}.json"
    if not replay_path.exists():
        raise ReplayNotFoundError(replay_id=replay_id, replay_dir=replay_dir)
    try:
        raw_json = replay_path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ReplayNotFoundError(replay_id=replay_id, replay_dir=replay_dir) from exc
    except UnicodeDecodeError as exc:
        raise ReplayParseError(path=replay_path, reason=str(exc)) from exc
    try:
        return ReplayRecord.model_validate_json(raw_json)
    except ValidationError as exc:
        raise ReplayParseError(path=replay_path, reason=str(exc)) from exc


def write_eval_result(result: EvalResult, eval_dir: Path) -> Path:
    target_path = eval_dir / f"{result.id}.json"
    _write_text_exclusive(target_path, result.model_dump_json(indent=2) + "\n")
    return target_path


def load_eval_result(eval_id: str, eval_dir: Path) -> EvalResult:
    eval_path = eval_dir / f"{eval_id}.json"
    if not eval_path.exists():
        raise EvalNotFoundError(eval_id=eval_id, eval_dir=eval_dir)
    return _load_eval_result_path(eval_path)


def list_eval_results(eval_dir: Path) -> tuple[EvalResult, ...]:
    if not eval_dir.exists():
        return ()
    eval_paths = sorted(eval_dir.glob("*.json"))
    return tuple(_load_eval_result_path(path) for path in eval_paths)


def _load_eval_result_path(eval_path: Path) -> EvalResult:
    try:
        raw_json = eval_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise EvalParseError(path=eval_path, reason=str(exc)) from exc
    try:
        return EvalResult.model_validate_json(raw_json)
    except ValidationError as exc:
        raise EvalParseError(path=eval_path, reason=str(exc)) from exc


def write_human_review(record: HumanReviewRecord, review_dir: Path) -> Path:
    target_path = review_dir / f"{record.id}.json"
    _write_text_exclusive(target_path, record.model_dump_json(indent=2) + "\n")
    return target_path


def write_learning_export(export: LearningExport, learning_dir: Path) -> Path:
    target_path = learning_dir / f"{export.id}.json"
    _write_text_exclusive(target_path, export.model_dump_json(indent=2) + "\n")
    return target_path


def write_context_bundle(bundle: ContextBundle, context_dir: Path) -> Path:
    target_path = context_dir / f"{bundle.id}.json"
    _write_text_exclusive(target_path, bundle.model_dump_json(indent=2) + "\n")
    return target_path


def write_reflection_report(report: ReflectionReport, reflection_dir: Path) -> Path:
    target_path = reflection_dir / f"{report.id}.json"
    _write_text_exclusive(target_path, report.model_dump_json(indent=2) + "\n")
    return target_path


def write_workflow_run(record: WorkflowRunRecord, workflow_dir: Path) -> Path:
    target_path = workflow_dir / f"{record.id}.json"
    _write_text_atomic(target_path, record.model_dump_json(indent=2) + "\n")
    return target_path


def load_workflow_run(run_id: str, workflow_dir: Path) -> WorkflowRunRecord:
    run_path = workflow_dir / f"{run_id}.json"
    if not run_path.exists():
        raise WorkflowRunNotFoundError(run_id=run_id, workflow_dir=workflow_dir)
    try:
        raw_json = run_path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise WorkflowRunNotFoundError(
            run_id=run_id,
            workflow_dir=workflow_dir,
        ) from exc
    except UnicodeDecodeError as exc:
        raise WorkflowRunParseError(path=run_path, reason=str(exc)) from exc
    try:
        return WorkflowRunRecord.model_validate_json(raw_json)
    except ValidationError as exc:
        raise WorkflowRunParseError(path=run_path, reason=str(exc)) from exc


def _write_text_exclusive(target_path: Path, content: str) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    if target_path.exists():
        raise DuplicateWriteError(path=target_path)

    with tempfile.NamedTemporaryFile(
        "w",
        delete=False,
        dir=target_path.parent,
        encoding="utf-8",
        prefix=f".{target_path.name}.",
        suffix=".tmp",
    ) as temp_file:
        temp_path = Path(temp_file.name)
        temp_file.write(content)

    try:
        os.link(temp_path, target_path)
    except FileExistsError as exc:
        raise DuplicateWriteError(path=target_path) from exc
    finally:
        if temp_path.exists():
            temp_path.unlink()


def _write_text_atomic(target_path: Path, content: str) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        delete=False,
        dir=target_path.parent,
        encoding="utf-8",
        prefix=f".{target_path.name}.",
        suffix=".tmp",
    ) as temp_file:
        temp_path = Path(temp_file.name)
        temp_file.write(content)

    try:
        temp_path.replace(target_path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def _manifest_yaml(manifest: CapabilityManifest) -> str:
    yaml_text: str = yaml.safe_dump(
        _manifest_yaml_data(manifest),
        sort_keys=False,
        allow_unicode=True,
    )
    return yaml_text


def _manifest_yaml_data(manifest: CapabilityManifest) -> dict[str, YamlValue]:
    return {
        "name": manifest.name,
        "version": manifest.version,
        "description": manifest.description,
        "status": manifest.status,
        "owner": manifest.owner,
        "dependencies": list(manifest.dependencies),
        "runtime_compatibility": list(manifest.runtime_compatibility),
        "evaluation_results": list(manifest.evaluation_results),
        "source_evidence_id": manifest.source_evidence_id,
        "normalized_goal": manifest.normalized_goal,
        "inputs": list(manifest.inputs),
        "context": {
            "required": list(manifest.context.required),
            "optional": list(manifest.context.optional),
            "forbidden": list(manifest.context.forbidden),
            "retrieval_query_template": manifest.context.retrieval_query_template,
            "summarization_rule": manifest.context.summarization_rule,
            "compression_rule": manifest.context.compression_rule,
            "freshness_rule": manifest.context.freshness_rule,
            "source_priority": list(manifest.context.source_priority),
            "maximum_token_budget": manifest.context.maximum_token_budget,
            "evidence_recall_strategy": manifest.context.evidence_recall_strategy,
        },
        "workflow": {
            "graph": manifest.workflow.graph,
            "nodes": list(manifest.workflow.nodes),
        },
        "harness": {
            "status": manifest.harness.status,
            "checks": list(manifest.harness.checks),
            "failures": list(manifest.harness.failures),
            "required_checks": list(manifest.harness.required_checks),
            "human_review_required": manifest.harness.human_review_required,
        },
        "runtime": {
            "name": manifest.runtime.name,
            "model": manifest.runtime.model,
            "preferred_models": list(manifest.runtime.preferred_models),
            "tools": list(manifest.runtime.tools),
        },
        "evidence": {
            "store": list(manifest.evidence.store),
        },
        "workflow_control": {
            "max_iterations": manifest.workflow_control.max_iterations,
            "max_runtime_seconds": manifest.workflow_control.max_runtime_seconds,
            "max_cost_usd": manifest.workflow_control.max_cost_usd,
            "allowed_tools": list(manifest.workflow_control.allowed_tools),
            "disallowed_tools": list(manifest.workflow_control.disallowed_tools),
            "require_approval_before_write": (
                manifest.workflow_control.require_approval_before_write
            ),
            "require_approval_before_external_call": (
                manifest.workflow_control.require_approval_before_external_call
            ),
            "require_approval_before_destructive_action": (
                manifest.workflow_control.require_approval_before_destructive_action
            ),
            "approval_required_actions": list(
                manifest.workflow_control.approval_required_actions,
            ),
            "safe_execution_mode": manifest.workflow_control.safe_execution_mode,
            "credential_scope": manifest.workflow_control.credential_scope,
            "network_policy": manifest.workflow_control.network_policy,
            "rollback_policy": manifest.workflow_control.rollback_policy,
            "checkpoint_interval": manifest.workflow_control.checkpoint_interval,
            "rollback_strategy": manifest.workflow_control.rollback_strategy,
            "resume_from_checkpoint": manifest.workflow_control.resume_from_checkpoint,
        },
        "human_review": {
            "status": manifest.human_review.status,
            "reviewer": manifest.human_review.reviewer,
            "notes": list(manifest.human_review.notes),
            "revision_request": manifest.human_review.revision_request,
            "reviewed_at": _datetime_yaml(manifest.human_review.reviewed_at),
        },
        "promotion_criteria": {
            "min_success_runs": manifest.promotion_criteria.min_success_runs,
            "max_human_intervention_rate": (
                manifest.promotion_criteria.max_human_intervention_rate
            ),
            "required_harness_pass_rate": (
                manifest.promotion_criteria.required_harness_pass_rate
            ),
        },
    }


def _datetime_yaml(value: datetime | None) -> str | None:
    if value is None:
        return None
    return str(value)
