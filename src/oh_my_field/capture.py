"""Compatibility shim: capture moved to oh_my_field.application.capture."""

from oh_my_field.application.capture import (
    CaptureDependencies,
    CaptureError,
    CaptureFileInput,
    CaptureRequest,
    CaptureStateError,
    CaptureSummary,
    InputFileReadError,
    run_capture_workflow,
)

__all__ = [
    "CaptureDependencies",
    "CaptureError",
    "CaptureFileInput",
    "CaptureRequest",
    "CaptureStateError",
    "CaptureSummary",
    "InputFileReadError",
    "run_capture_workflow",
]
