"""Compatibility shim: eval moved to oh_my_field.application.eval."""

from oh_my_field.application.eval import (
    EvalError,
    EvalRequest,
    EvalSummary,
    run_eval_workflow,
)

__all__ = [
    "EvalError",
    "EvalRequest",
    "EvalSummary",
    "run_eval_workflow",
]
