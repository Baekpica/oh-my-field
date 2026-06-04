"""Compatibility shim: moved to oh_my_field.infrastructure.fs.hashing."""

from oh_my_field.infrastructure.fs.hashing import (
    append_integrity_link,
    integrity_link,
    model_sha256,
)

__all__ = [
    "append_integrity_link",
    "integrity_link",
    "model_sha256",
]
