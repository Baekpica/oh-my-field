import hashlib
import json

from pydantic import BaseModel

from oh_my_field.models import ArtifactIntegrityLink


def model_sha256(model: BaseModel) -> str:
    payload = json.dumps(
        model.model_dump(mode="json", exclude={"integrity_chain"}),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def integrity_link(
    *,
    artifact_type: str,
    artifact_id: str,
    model: BaseModel,
    previous_sha256: str | None = None,
) -> ArtifactIntegrityLink:
    return ArtifactIntegrityLink(
        artifact_type=artifact_type,
        artifact_id=artifact_id,
        sha256=model_sha256(model),
        previous_sha256=previous_sha256,
    )


def append_integrity_link[ModelT: BaseModel](
    model: ModelT,
    *,
    artifact_type: str,
    artifact_id: str,
    previous_sha256: str | None = None,
) -> ModelT:
    link = integrity_link(
        artifact_type=artifact_type,
        artifact_id=artifact_id,
        model=model,
        previous_sha256=previous_sha256,
    )
    existing = tuple(getattr(model, "integrity_chain", ()))
    return model.model_copy(update={"integrity_chain": (*existing, link)})
