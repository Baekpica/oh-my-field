import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Final, cast

import yaml
from pydantic import BaseModel, ValidationError

from oh_my_field.models import (
    CapabilityExportBundle,
    CapabilityManifest,
    ContextBundle,
    EvalResult,
    EvalSet,
    EvidenceRecord,
    HumanReviewRecord,
    LearningExport,
    LearningPatchDecision,
    ReflectionReport,
    ReplayRecord,
    WorkflowRunRecord,
)

type YamlValue = (
    str | int | float | bool | None | list["YamlValue"] | dict[str, "YamlValue"]
)
CAPABILITY_FILE_NAME: Final = "capability.yaml"
LEGACY_MANIFEST_FILE_NAME: Final = "manifest.yaml"


class StorageError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class CapabilityPackagePaths:
    package_dir: Path
    capability_path: Path
    instructions_path: Path
    harness_path: Path
    card_path: Path


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


@dataclass
class ArtifactNotFoundError(StorageError):
    artifact_type: str
    artifact_id: str
    artifact_dir: Path

    def __str__(self) -> str:
        return (
            f"{self.artifact_type} {self.artifact_id!r} not found in "
            f"{self.artifact_dir}"
        )


@dataclass
class ArtifactParseError(StorageError):
    artifact_type: str
    path: Path
    reason: str

    def __str__(self) -> str:
        return (
            f"could not parse {self.artifact_type} file {self.path}: "
            f"{self.reason}"
        )


def write_evidence(record: EvidenceRecord, evidence_dir: Path) -> Path:
    target_path = evidence_dir / f"{record.id}.json"
    _write_text_exclusive(target_path, record.model_dump_json(indent=2) + "\n")
    return target_path


def write_manifest(manifest: CapabilityManifest, capabilities_dir: Path) -> Path:
    return write_capability_package(manifest, capabilities_dir).capability_path


def write_capability_package(
    manifest: CapabilityManifest,
    capabilities_dir: Path,
) -> CapabilityPackagePaths:
    paths = capability_package_paths(manifest.name, capabilities_dir)
    _write_text_exclusive(paths.capability_path, _manifest_yaml(manifest))
    _write_text_exclusive(
        paths.instructions_path,
        _capability_instructions_markdown(manifest),
    )
    _write_text_exclusive(paths.harness_path, _capability_harness_yaml(manifest))
    _write_text_exclusive(paths.card_path, _capability_card_markdown(manifest))
    return paths


def update_manifest(manifest: CapabilityManifest, capabilities_dir: Path) -> Path:
    paths = capability_package_paths(manifest.name, capabilities_dir)
    _write_text_atomic(paths.capability_path, _manifest_yaml(manifest))
    _write_text_atomic(
        paths.instructions_path,
        _capability_instructions_markdown(manifest),
    )
    _write_text_atomic(paths.harness_path, _capability_harness_yaml(manifest))
    _write_text_atomic(paths.card_path, _capability_card_markdown(manifest))
    return paths.capability_path


def load_manifest(capability_name: str, capabilities_dir: Path) -> CapabilityManifest:
    manifest_path = manifest_path_for_capability(capability_name, capabilities_dir)
    if manifest_path is None:
        raise ManifestNotFoundError(
            capability_name=capability_name,
            capabilities_dir=capabilities_dir,
        )
    return _load_manifest_path(manifest_path)


def capability_package_paths(
    capability_name: str,
    capabilities_dir: Path,
) -> CapabilityPackagePaths:
    package_dir = capabilities_dir / capability_name
    return CapabilityPackagePaths(
        package_dir=package_dir,
        capability_path=package_dir / CAPABILITY_FILE_NAME,
        instructions_path=package_dir / "instructions.md",
        harness_path=package_dir / "harness.yaml",
        card_path=package_dir / "README.md",
    )


def manifest_path_for_capability(
    capability_name: str,
    capabilities_dir: Path,
) -> Path | None:
    package_dir = capabilities_dir / capability_name
    for file_name in (CAPABILITY_FILE_NAME, LEGACY_MANIFEST_FILE_NAME):
        candidate = package_dir / file_name
        if candidate.exists():
            return candidate
    return None


def list_manifests(
    capabilities_dir: Path,
) -> tuple[tuple[Path, CapabilityManifest], ...]:
    if not capabilities_dir.exists():
        return ()
    manifest_paths = tuple(
        path
        for package_dir in sorted(path for path in capabilities_dir.iterdir())
        if package_dir.is_dir()
        for path in (
            manifest_path_for_capability(package_dir.name, capabilities_dir),
        )
        if path is not None
    )
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


def write_eval_set(eval_set: EvalSet, eval_set_dir: Path) -> Path:
    target_path = eval_set_dir / f"{eval_set.name}.json"
    _write_text_atomic(target_path, eval_set.model_dump_json(indent=2) + "\n")
    return target_path


def load_eval_set(eval_set_name: str, eval_set_dir: Path) -> EvalSet:
    eval_set_path = _artifact_path(eval_set_name, eval_set_dir)
    return _load_artifact(
        "eval set",
        eval_set_name,
        eval_set_dir,
        eval_set_path,
        EvalSet,
    )


def list_eval_sets(eval_set_dir: Path) -> tuple[EvalSet, ...]:
    return _list_artifacts("eval set", eval_set_dir, EvalSet)


def write_human_review(record: HumanReviewRecord, review_dir: Path) -> Path:
    target_path = review_dir / f"{record.id}.json"
    _write_text_exclusive(target_path, record.model_dump_json(indent=2) + "\n")
    return target_path


def load_human_review(review_id: str, review_dir: Path) -> HumanReviewRecord:
    review_path = _artifact_path(review_id, review_dir)
    return _load_artifact(
        "review",
        review_id,
        review_dir,
        review_path,
        HumanReviewRecord,
    )


def list_human_reviews(review_dir: Path) -> tuple[HumanReviewRecord, ...]:
    return _list_artifacts("review", review_dir, HumanReviewRecord)


def write_learning_export(export: LearningExport, learning_dir: Path) -> Path:
    target_path = learning_dir / f"{export.id}.json"
    _write_text_exclusive(target_path, export.model_dump_json(indent=2) + "\n")
    return target_path


def write_learning_patch_decision(
    decision: LearningPatchDecision,
    learning_patch_dir: Path,
) -> Path:
    target_path = learning_patch_dir / f"{decision.id}.json"
    _write_text_exclusive(target_path, decision.model_dump_json(indent=2) + "\n")
    return target_path


def load_learning_patch_decision(
    decision_id: str,
    learning_patch_dir: Path,
) -> LearningPatchDecision:
    decision_path = _artifact_path(decision_id, learning_patch_dir)
    return _load_artifact(
        "learning patch decision",
        decision_id,
        learning_patch_dir,
        decision_path,
        LearningPatchDecision,
    )


def list_learning_patch_decisions(
    learning_patch_dir: Path,
) -> tuple[LearningPatchDecision, ...]:
    return _list_artifacts(
        "learning patch decision",
        learning_patch_dir,
        LearningPatchDecision,
    )


def write_context_bundle(bundle: ContextBundle, context_dir: Path) -> Path:
    target_path = context_dir / f"{bundle.id}.json"
    _write_text_exclusive(target_path, bundle.model_dump_json(indent=2) + "\n")
    return target_path


def load_context_bundle(context_id: str, context_dir: Path) -> ContextBundle:
    context_path = _artifact_path(context_id, context_dir)
    return _load_artifact(
        "context",
        context_id,
        context_dir,
        context_path,
        ContextBundle,
    )


def list_context_bundles(context_dir: Path) -> tuple[ContextBundle, ...]:
    return _list_artifacts("context", context_dir, ContextBundle)


def write_reflection_report(report: ReflectionReport, reflection_dir: Path) -> Path:
    target_path = reflection_dir / f"{report.id}.json"
    _write_text_exclusive(target_path, report.model_dump_json(indent=2) + "\n")
    return target_path


def load_learning_export(learning_id: str, learning_dir: Path) -> LearningExport:
    learning_path = _artifact_path(learning_id, learning_dir)
    return _load_artifact(
        "learning",
        learning_id,
        learning_dir,
        learning_path,
        LearningExport,
    )


def list_learning_exports(learning_dir: Path) -> tuple[LearningExport, ...]:
    return _list_artifacts("learning", learning_dir, LearningExport)


def load_reflection_report(
    reflection_id: str,
    reflection_dir: Path,
) -> ReflectionReport:
    reflection_path = _artifact_path(reflection_id, reflection_dir)
    return _load_artifact(
        "reflection",
        reflection_id,
        reflection_dir,
        reflection_path,
        ReflectionReport,
    )


def list_reflection_reports(reflection_dir: Path) -> tuple[ReflectionReport, ...]:
    return _list_artifacts("reflection", reflection_dir, ReflectionReport)


def write_export_bundle(bundle: CapabilityExportBundle, export_dir: Path) -> Path:
    target_path = export_dir / bundle.capability_name / f"{bundle.id}.json"
    _write_text_exclusive(target_path, bundle.model_dump_json(indent=2) + "\n")
    return target_path


def load_export_bundle(export_id: str, export_dir: Path) -> CapabilityExportBundle:
    for export_path in sorted(export_dir.glob(f"*/{export_id}.json")):
        return _load_artifact_path("export", export_path, CapabilityExportBundle)
    raise ArtifactNotFoundError(
        artifact_type="export",
        artifact_id=export_id,
        artifact_dir=export_dir,
    )


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


def _artifact_path(artifact_id: str, artifact_dir: Path) -> Path:
    return artifact_dir / f"{artifact_id}.json"


def _load_artifact[ModelT: BaseModel](
    artifact_type: str,
    artifact_id: str,
    artifact_dir: Path,
    artifact_path: Path,
    model: type[ModelT],
) -> ModelT:
    if not artifact_path.exists():
        raise ArtifactNotFoundError(
            artifact_type=artifact_type,
            artifact_id=artifact_id,
            artifact_dir=artifact_dir,
        )
    return _load_artifact_path(artifact_type, artifact_path, model)


def _list_artifacts[ModelT: BaseModel](
    artifact_type: str,
    artifact_dir: Path,
    model: type[ModelT],
) -> tuple[ModelT, ...]:
    if not artifact_dir.exists():
        return ()
    return tuple(
        _load_artifact_path(artifact_type, path, model)
        for path in sorted(artifact_dir.glob("*.json"))
    )


def _load_artifact_path[ModelT: BaseModel](
    artifact_type: str,
    artifact_path: Path,
    model: type[ModelT],
) -> ModelT:
    try:
        raw_json = artifact_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ArtifactParseError(
            artifact_type=artifact_type,
            path=artifact_path,
            reason=str(exc),
        ) from exc
    try:
        return model.model_validate_json(raw_json)
    except ValidationError as exc:
        raise ArtifactParseError(
            artifact_type=artifact_type,
            path=artifact_path,
            reason=str(exc),
        ) from exc


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
    return cast("dict[str, YamlValue]", manifest.model_dump(mode="json"))


def _capability_instructions_markdown(manifest: CapabilityManifest) -> str:
    lines = [
        f"# {manifest.name}",
        "",
        "## Purpose",
        manifest.description,
        "",
        "## Runtime-Neutral Instructions",
        f"- Use this capability for: {manifest.normalized_goal}",
        "- Treat the package as the source of truth, not an agent runtime.",
        "- Select context using the context policy before asking an agent to act.",
        "- Run the harness checks before marking the work complete.",
        "- Preserve new failures as evidence for future portability fixes.",
        "",
        "## Required Context",
        *_markdown_list(manifest.context.required, "No required context recorded."),
        "",
        "## Forbidden Context",
        *_markdown_list(
            manifest.context.forbidden,
            "No forbidden context recorded.",
        ),
        "",
        "## Harness Checks",
        *_markdown_list(
            manifest.harness.required_checks,
            "No required checks recorded.",
        ),
        "",
        "## Runtime Coverage",
        *_markdown_list(_runtime_profile_lines(manifest), "No runtime recorded."),
        "",
    ]
    return "\n".join(lines)


def _capability_harness_yaml(manifest: CapabilityManifest) -> str:
    data = cast(
        "dict[str, YamlValue]",
        {
            "capability": manifest.name,
            "status": manifest.harness.status,
            "required_checks": list(manifest.harness.required_checks),
            "observed_checks": list(manifest.harness.checks),
            "failures": list(manifest.harness.failures),
            "human_review_required": manifest.harness.human_review_required,
            "workflow_control": {
                "safe_execution_mode": manifest.workflow_control.safe_execution_mode,
                "network_policy": manifest.workflow_control.network_policy,
                "approval_required_actions": list(
                    manifest.workflow_control.approval_required_actions,
                ),
                "allowed_tools": list(manifest.workflow_control.allowed_tools),
                "disallowed_tools": list(manifest.workflow_control.disallowed_tools),
            },
        },
    )
    yaml_text: str = yaml.safe_dump(data, sort_keys=False, allow_unicode=True)
    return yaml_text


def _capability_card_markdown(manifest: CapabilityManifest) -> str:
    lines = [
        f"# {manifest.name}",
        "",
        "## What It Does",
        manifest.description,
        "",
        "## When To Use",
        f"- {manifest.normalized_goal}",
        "",
        "## Package Contents",
        f"- `{CAPABILITY_FILE_NAME}`: canonical capability metadata.",
        "- `instructions.md`: runtime-neutral agent instruction surface.",
        "- `harness.yaml`: verification and approval checks.",
        "- `README.md`: human-readable capability card.",
        "",
        "## Required Context",
        *_markdown_list(manifest.context.required, "No required context recorded."),
        "",
        "## Harness",
        f"- Status: {manifest.harness.status}",
        *_markdown_list(
            manifest.harness.required_checks,
            "No required checks recorded.",
        ),
        "",
        "## Runtime Coverage",
        *_markdown_list(_runtime_profile_lines(manifest), "No runtime recorded."),
        "",
        "## Portability",
        f"- Source runtime: {manifest.runtime.name}",
        f"- Source model: {manifest.runtime.model or 'not recorded'}",
        "- Target exports: not exported",
        "- Target validation: not run",
        "",
        "## Status",
        f"- Lifecycle: {manifest.status}",
        f"- Version: {manifest.version}",
        f"- Source evidence: {manifest.source_evidence_id}",
        "",
        "## Last Learning Patches",
        *_markdown_list(_patch_lines(manifest), "No accepted patches recorded."),
        "",
    ]
    return "\n".join(lines)


def _markdown_list(values: tuple[str, ...], empty: str) -> list[str]:
    if not values:
        return [f"- {empty}"]
    return [f"- {value}" for value in values]


def _runtime_profile_lines(manifest: CapabilityManifest) -> tuple[str, ...]:
    values = [f"runtime: {manifest.runtime.name}"]
    if manifest.runtime.model is not None:
        values.append(f"model: {manifest.runtime.model}")
    values.extend(
        f"preferred model: {model}" for model in manifest.runtime.preferred_models
    )
    values.extend(f"tool: {tool}" for tool in manifest.runtime.tools)
    return tuple(values)


def _patch_lines(manifest: CapabilityManifest) -> tuple[str, ...]:
    return (
        *(f"prompt: {patch}" for patch in manifest.patches.prompt),
        *(f"context: {patch}" for patch in manifest.patches.context),
        *(f"harness: {patch}" for patch in manifest.patches.harness),
    )
