"""Compatibility shim: inspection moved to the application layer.

Importing from ``oh_my_field.inspection`` keeps working while internal callers
migrate to ``oh_my_field.application.inspection``.
"""

from oh_my_field.application.inspection import (
    InspectRequest,
    InspectSummary,
    InvalidInspectTargetError,
    inspect_artifact,
)

__all__ = [
    "InspectRequest",
    "InspectSummary",
    "InvalidInspectTargetError",
    "inspect_artifact",
]
