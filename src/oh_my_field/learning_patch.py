import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from pydantic import Field

from oh_my_field.integrity import append_integrity_link, integrity_link
from oh_my_field.models import (
    CAPABILITY_NAME_PATTERN,
    EVIDENCE_ID_PATTERN,
    ArtifactIntegrityLink,
    CapabilityManifest,
    LearningExport,
    LearningPatchDecision,
    PatchDecisionStatus,
    PatchKind,
    StrictModel,
)
from oh_my_field.storage import (
    load_learning_export,
    load_manifest,
    update_manifest,
    write_learning_patch_decision,
)

type Clock = Callable[[], datetime]
type TokenFactory = Callable[[], str]


class LearningPatchError(Exception):
    pass


@dataclass
class LearningPatchIndexError(LearningPatchError):
    index: int
    patch_count: int

    def __str__(self) -> str:
        return (
            f"patch index {self.index} is out of range for "
            f"{self.patch_count} prompt patches"
        )


@dataclass(frozen=True, slots=True)
class LearningPatchDependencies:
    clock: Clock
    token_factory: TokenFactory


class LearningPatchRequest(StrictModel):
    capability_name: str = Field(pattern=CAPABILITY_NAME_PATTERN)
    learning_id: str = Field(pattern=EVIDENCE_ID_PATTERN)
    patch_kind: PatchKind = "prompt"
    patch_index: int = Field(ge=1)
    decision: PatchDecisionStatus
    reviewer: str | None = None
    notes: tuple[str, ...] = ()
    before_eval_id: str | None = Field(default=None, pattern=EVIDENCE_ID_PATTERN)
    after_eval_id: str | None = Field(default=None, pattern=EVIDENCE_ID_PATTERN)
    pass_rate_delta: float | None = None
    capabilities_dir: Path
    learning_dir: Path
    learning_patch_dir: Path


class LearningPatchSummary(StrictModel):
    decision_id: str
    decision_path: str
    capability_name: str
    decision: PatchDecisionStatus
    patch_kind: PatchKind
    manifest_path: str | None


def apply_learning_patch(
    request: LearningPatchRequest,
    dependencies: LearningPatchDependencies | None = None,
) -> LearningPatchSummary:
    dependencies = dependencies or _default_dependencies()
    manifest = load_manifest(request.capability_name, request.capabilities_dir)
    learning_export = load_learning_export(request.learning_id, request.learning_dir)
    patch = _select_patch(learning_export, request.patch_kind, request.patch_index)
    manifest_path: str | None = None
    if request.decision == "accepted":
        updated_manifest = _accepted_manifest(manifest, request.patch_kind, patch)
        manifest_path = str(update_manifest(updated_manifest, request.capabilities_dir))
    created_at = dependencies.clock().astimezone(UTC)
    decision = LearningPatchDecision(
        id=f"{created_at:%Y%m%dT%H%M%SZ}-{dependencies.token_factory()}",
        created_at=created_at,
        capability_name=request.capability_name,
        learning_id=request.learning_id,
        patch_kind=request.patch_kind,
        patch=patch,
        decision=request.decision,
        reviewer=request.reviewer,
        notes=request.notes,
        manifest_path=manifest_path,
        before_eval_id=request.before_eval_id,
        after_eval_id=request.after_eval_id,
        pass_rate_delta=request.pass_rate_delta,
        integrity_chain=(_learning_integrity_link(learning_export),),
    )
    decision = append_integrity_link(
        decision,
        artifact_type="learning_patch_decision",
        artifact_id=decision.id,
        previous_sha256=decision.integrity_chain[-1].sha256,
    )
    decision_path = write_learning_patch_decision(
        decision,
        request.learning_patch_dir,
    )
    return LearningPatchSummary(
        decision_id=decision.id,
        decision_path=str(decision_path),
        capability_name=request.capability_name,
        decision=decision.decision,
        patch_kind=request.patch_kind,
        manifest_path=manifest_path,
    )


def _default_dependencies() -> LearningPatchDependencies:
    return LearningPatchDependencies(clock=_now_utc, token_factory=_token_suffix)


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _token_suffix() -> str:
    return secrets.token_hex(4)


def _select_patch(
    learning_export: LearningExport,
    patch_kind: PatchKind,
    patch_index: int,
) -> str:
    patches = _patches_for_kind(learning_export, patch_kind)
    try:
        return patches[patch_index - 1]
    except IndexError as exc:
        raise LearningPatchIndexError(
            index=patch_index,
            patch_count=len(patches),
        ) from exc


def _patches_for_kind(
    learning_export: LearningExport,
    patch_kind: PatchKind,
) -> tuple[str, ...]:
    if patch_kind == "context":
        return learning_export.context_patches
    if patch_kind == "harness":
        return learning_export.harness_patches
    return learning_export.prompt_patches


def _accepted_manifest(
    manifest: CapabilityManifest,
    patch_kind: PatchKind,
    patch: str,
) -> CapabilityManifest:
    if patch_kind == "context":
        existing = manifest.patches.context
    elif patch_kind == "harness":
        existing = manifest.patches.harness
    else:
        existing = manifest.patches.prompt
    patches = manifest.patches.model_copy(
        update={patch_kind: (*existing, patch)},
    )
    updated = manifest.model_copy(update={"patches": patches})
    previous_sha256 = (
        manifest.integrity_chain[-1].sha256 if manifest.integrity_chain else None
    )
    return append_integrity_link(
        updated,
        artifact_type="capability",
        artifact_id=updated.name,
        previous_sha256=previous_sha256,
    )


def _learning_integrity_link(
    learning_export: LearningExport,
) -> ArtifactIntegrityLink:
    if learning_export.integrity_chain:
        return learning_export.integrity_chain[-1]
    return integrity_link(
        artifact_type="learning",
        artifact_id=learning_export.id,
        model=learning_export,
    )
