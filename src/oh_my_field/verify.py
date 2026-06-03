from pathlib import Path
from typing import Literal, cast

from pydantic import BaseModel, Field

from oh_my_field.integrity import model_sha256
from oh_my_field.models import (
    ArtifactIntegrityLink,
    CapabilityManifest,
    IntegrityVerificationCheck,
    IntegrityVerificationResult,
    StrictModel,
)
from oh_my_field.storage import (
    StorageError,
    load_context_bundle,
    load_eval_result,
    load_evidence,
    load_export_bundle,
    load_human_review,
    load_learning_export,
    load_learning_patch_decision,
    load_manifest,
    load_reflection_report,
    load_replay,
)

type VerifyTargetType = Literal[
    "evidence",
    "capability",
    "replay",
    "eval",
    "context",
    "learning",
    "learning_patch",
    "reflection",
    "review",
    "export",
]


class VerifyError(Exception):
    pass


class VerifyRequest(StrictModel):
    target_type: VerifyTargetType
    target_id: str = Field(min_length=1)
    capabilities_dir: Path = Path("capabilities")
    evidence_dir: Path = Path(".omf/evidence")
    replay_dir: Path = Path(".omf/replays")
    eval_dir: Path = Path(".omf/evals")
    context_dir: Path = Path(".omf/context")
    learning_dir: Path = Path(".omf/learning")
    learning_patch_dir: Path = Path(".omf/learning_patches")
    reflection_dir: Path = Path(".omf/reflections")
    review_dir: Path = Path(".omf/reviews")
    export_dir: Path = Path(".omf/exports")


def verify_artifact(request: VerifyRequest) -> IntegrityVerificationResult:
    artifact_type, artifact = _load_target(request)
    checks = (
        *_self_checks(artifact_type, request.target_id, artifact),
        *_capability_source_checks(artifact, request),
    )
    status = "fail" if any(check.status == "fail" for check in checks) else "pass"
    return IntegrityVerificationResult(
        target_type=request.target_type,
        target_id=request.target_id,
        status=status,
        checks=checks,
    )


def _load_target(request: VerifyRequest) -> tuple[str, BaseModel]:
    artifact_type: str
    artifact: BaseModel
    if request.target_type == "evidence":
        artifact_type = "evidence"
        artifact = load_evidence(request.target_id, request.evidence_dir)
    elif request.target_type == "capability":
        artifact_type = "capability"
        artifact = load_manifest(request.target_id, request.capabilities_dir)
    elif request.target_type == "replay":
        artifact_type = "replay"
        artifact = load_replay(request.target_id, request.replay_dir)
    elif request.target_type == "eval":
        artifact_type = "eval"
        artifact = load_eval_result(request.target_id, request.eval_dir)
    elif request.target_type == "context":
        artifact_type = "context"
        artifact = load_context_bundle(request.target_id, request.context_dir)
    elif request.target_type == "learning":
        artifact_type = "learning"
        artifact = load_learning_export(request.target_id, request.learning_dir)
    elif request.target_type == "learning_patch":
        artifact_type = "learning_patch_decision"
        artifact = load_learning_patch_decision(
            request.target_id,
            request.learning_patch_dir,
        )
    elif request.target_type == "reflection":
        artifact_type = "reflection"
        artifact = load_reflection_report(request.target_id, request.reflection_dir)
    elif request.target_type == "review":
        artifact_type = "review"
        artifact = load_human_review(request.target_id, request.review_dir)
    else:
        artifact_type = "export"
        artifact = load_export_bundle(request.target_id, request.export_dir)
    return artifact_type, artifact


def _self_checks(
    artifact_type: str,
    artifact_id: str,
    artifact: BaseModel,
) -> tuple[IntegrityVerificationCheck, ...]:
    chain = _integrity_chain(artifact)
    if not chain:
        return (
            IntegrityVerificationCheck(
                artifact_type=artifact_type,
                artifact_id=artifact_id,
                status="fail",
                message="artifact has no integrity chain",
            ),
        )
    checks = [
        _self_hash_check(artifact_type, artifact_id, artifact, chain[-1]),
        _self_identity_check(artifact_type, artifact_id, chain[-1]),
    ]
    checks.extend(_previous_link_checks(artifact_type, artifact_id, chain))
    return tuple(checks)


def _self_hash_check(
    artifact_type: str,
    artifact_id: str,
    artifact: BaseModel,
    link: ArtifactIntegrityLink,
) -> IntegrityVerificationCheck:
    actual_sha256 = model_sha256(artifact)
    status = "pass" if actual_sha256 == link.sha256 else "fail"
    message = (
        "artifact hash matches integrity link"
        if status == "pass"
        else "artifact hash does not match integrity link"
    )
    return IntegrityVerificationCheck(
        artifact_type=artifact_type,
        artifact_id=artifact_id,
        status=status,
        message=message,
        expected_sha256=link.sha256,
        actual_sha256=actual_sha256,
    )


def _self_identity_check(
    artifact_type: str,
    artifact_id: str,
    link: ArtifactIntegrityLink,
) -> IntegrityVerificationCheck:
    identity_matches = (
        link.artifact_type == artifact_type and link.artifact_id == artifact_id
    )
    return IntegrityVerificationCheck(
        artifact_type=artifact_type,
        artifact_id=artifact_id,
        status="pass" if identity_matches else "fail",
        message=(
            "integrity link identity matches artifact"
            if identity_matches
            else (
                "integrity link identity "
                f"{link.artifact_type}:{link.artifact_id} does not match artifact"
            )
        ),
        expected_sha256=link.sha256,
        actual_sha256=link.sha256,
    )


def _previous_link_checks(
    artifact_type: str,
    artifact_id: str,
    chain: tuple[ArtifactIntegrityLink, ...],
) -> tuple[IntegrityVerificationCheck, ...]:
    checks: list[IntegrityVerificationCheck] = []
    for index, link in enumerate(chain):
        if link.previous_sha256 is None:
            continue
        matched = any(
            previous.sha256 == link.previous_sha256 for previous in chain[:index]
        )
        checks.append(
            IntegrityVerificationCheck(
                artifact_type=artifact_type,
                artifact_id=artifact_id,
                status="pass" if matched else "fail",
                message=(
                    "previous hash points to an earlier integrity link"
                    if matched
                    else "previous hash does not point to an earlier integrity link"
                ),
                expected_sha256=link.previous_sha256,
                actual_sha256=link.previous_sha256 if matched else None,
            ),
        )
    return tuple(checks)


def _capability_source_checks(
    artifact: BaseModel,
    request: VerifyRequest,
) -> tuple[IntegrityVerificationCheck, ...]:
    if not isinstance(artifact, CapabilityManifest):
        return ()
    checks: list[IntegrityVerificationCheck] = []
    for link in artifact.integrity_chain:
        if link.artifact_type != "evidence":
            continue
        try:
            evidence = load_evidence(link.artifact_id, request.evidence_dir)
        except StorageError as exc:
            checks.append(
                IntegrityVerificationCheck(
                    artifact_type="evidence",
                    artifact_id=link.artifact_id,
                    status="fail",
                    message=str(exc),
                    expected_sha256=link.sha256,
                ),
            )
            continue
        actual_sha256 = model_sha256(evidence)
        status = "pass" if actual_sha256 == link.sha256 else "fail"
        checks.append(
            IntegrityVerificationCheck(
                artifact_type="evidence",
                artifact_id=link.artifact_id,
                status=status,
                message=(
                    "source evidence hash matches capability link"
                    if status == "pass"
                    else "source evidence hash does not match capability link"
                ),
                expected_sha256=link.sha256,
                actual_sha256=actual_sha256,
            ),
        )
    return tuple(checks)


def _integrity_chain(artifact: BaseModel) -> tuple[ArtifactIntegrityLink, ...]:
    return cast(
        "tuple[ArtifactIntegrityLink, ...]",
        getattr(artifact, "integrity_chain", ()),
    )
