from oh_my_field.domain.models import (
    PortabilityHealth,
    TargetStatusEntry,
    TargetValidationStatus,
)
from oh_my_field.domain.portability.models import (
    ExportTarget,
    PortabilityTarget,
    ValidationStatus,
)

# Conventional "run the target agent" commands per runtime. These mirror the
# documented examples in docs/runtime-adapters/*.md and are *suggestions* an
# agent starts from, never guaranteed-correct invocations. Runtimes without a
# documented convention (e.g. odysseus) intentionally have no entry so callers
# fall back to an honest "<your runtime run command>" placeholder.
_RUN_COMMAND_TEMPLATES: dict[ExportTarget, str] = {
    "codex": "codex exec --full-auto < task.md",
    "claude_code": "claude < task.md",
    "hermes": "hermes-code --profile target --skill {name}",
    "pi": "pi -p 'Run the {name} capability against this project'",
    "generic": "./run-capability-check.sh",
}

_KNOWN_TARGET_VALIDATION_STATUSES: tuple[TargetValidationStatus, ...] = (
    "not_run",
    "needs_validation",
    "needs_adaptation",
    "validated",
)


def normalize_target_validation_status(status: object) -> TargetValidationStatus:
    if status in _KNOWN_TARGET_VALIDATION_STATUSES:
        return status
    return "needs_validation"


def build_portability_health(
    *,
    export_count: int,
    targets: tuple[TargetStatusEntry, ...],
) -> PortabilityHealth:
    return PortabilityHealth(
        export_status="exported" if export_count else "not_exported",
        import_status="imported" if targets else "not_imported",
        validation_status=aggregate_target_validation_status(targets),
        export_count=export_count,
        import_count=len(targets),
        target_validation_count=sum(1 for target in targets if target.eval_recorded),
        target_statuses=targets,
    )


def aggregate_target_validation_status(
    targets: tuple[TargetStatusEntry, ...],
) -> TargetValidationStatus:
    if not targets:
        return "not_run"
    statuses = {target.validation_status for target in targets}
    if "needs_adaptation" in statuses:
        return "needs_adaptation"
    if "needs_validation" in statuses:
        return "needs_validation"
    if statuses == {"validated"}:
        return "validated"
    return "needs_validation"


def next_validation_action(status: ValidationStatus) -> str:
    if status == "needs_adaptation":
        return "review unavailable tools and adapt the target package"
    if status == "validated":
        return "target import validated; monitor or promote the capability"
    return (
        "pending: no target run observed yet; run the target with "
        "--run-command to complete validation (this is not a failure)"
    )


def target_flags(target: PortabilityTarget) -> str:
    flags = f"--target {target.runtime}"
    if target.model is not None:
        flags += f" --model {target.model}"
    return flags


def suggested_run_command(name: str, target: PortabilityTarget) -> str | None:
    """Return a conventional target-run command for the runtime, or None.

    The result is a starting point the agent should confirm against its actual
    install, not a guaranteed-correct invocation. Returns None for runtimes
    without a documented convention so callers emit an honest placeholder.
    """
    template = _RUN_COMMAND_TEMPLATES.get(target.runtime)
    if template is None:
        return None
    return template.format(name=name)


def validate_command_hint(name: str, target: PortabilityTarget, flags: str) -> str:
    """Build the `omf capability validate ... --run-command "..."` suggestion.

    Always pairs the validate command with a real (or honestly placeholdered)
    run command so following it can actually reach the terminal `validated`
    state instead of looping back to `needs_validation`.
    """
    suggested = suggested_run_command(name, target)
    run = suggested if suggested is not None else f"<your {target.runtime} run command>"
    return f'omf capability validate {name} {flags} --run-command "{run}"'
