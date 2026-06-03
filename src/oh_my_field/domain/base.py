"""Shared domain base model and cross-cutting artifact constants.

``StrictModel`` is the frozen, extra-forbidding pydantic base every domain
model derives from. The schema-version and id/hash patterns are cross-cutting
artifact constants used across evidence, capability, and portability concepts.
"""

from oh_my_field.domain.models import (
    CAPABILITY_NAME_PATTERN,
    CAPABILITY_SCHEMA_VERSION,
    COMMAND_RISK_CATEGORIES,
    EVAL_RESULT_SCHEMA_VERSION,
    EVIDENCE_ID_PATTERN,
    EVIDENCE_SCHEMA_VERSION,
    LEARNING_EXPORT_SCHEMA_VERSION,
    LEARNING_PATCH_DECISION_SCHEMA_VERSION,
    SHA256_PATTERN,
    StrictModel,
)

__all__ = [
    "CAPABILITY_NAME_PATTERN",
    "CAPABILITY_SCHEMA_VERSION",
    "COMMAND_RISK_CATEGORIES",
    "EVAL_RESULT_SCHEMA_VERSION",
    "EVIDENCE_ID_PATTERN",
    "EVIDENCE_SCHEMA_VERSION",
    "LEARNING_EXPORT_SCHEMA_VERSION",
    "LEARNING_PATCH_DECISION_SCHEMA_VERSION",
    "SHA256_PATTERN",
    "StrictModel",
]
