"""Compatibility shim: verify moved to oh_my_field.application.verify.

Importing from ``oh_my_field.verify`` keeps working while internal callers
migrate to the application layer path.
"""

from oh_my_field.application.verify import (
    VerifyError,
    VerifyRequest,
    verify_artifact,
)

__all__ = [
    "VerifyError",
    "VerifyRequest",
    "verify_artifact",
]
