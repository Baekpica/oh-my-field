from dataclasses import dataclass
from pathlib import Path

from pydantic import Field

from oh_my_field.models import (
    CAPABILITY_NAME_PATTERN,
    EvalCase,
    EvalCaseInput,
    EvalExpectedCheck,
    EvalSet,
    StrictModel,
)
from oh_my_field.storage import ArtifactNotFoundError, load_eval_set, write_eval_set


class EvalSetError(Exception):
    pass


@dataclass
class EvalCaseInputParseError(EvalSetError):
    value: str

    def __str__(self) -> str:
        return f"eval case input must use key=value, got {self.value!r}"


class RegressionCaseRequest(StrictModel):
    capability_name: str = Field(pattern=CAPABILITY_NAME_PATTERN)
    eval_set_name: str = Field(pattern=CAPABILITY_NAME_PATTERN)
    eval_set_version: str = Field(min_length=1)
    case_id: str = Field(pattern=CAPABILITY_NAME_PATTERN)
    inputs: tuple[str, ...] = ()
    expected_checks: tuple[str, ...] = ()
    flaky_checks: tuple[str, ...] = ()
    harness_commands: tuple[str, ...] = ()
    eval_set_dir: Path


class RegressionCaseSummary(StrictModel):
    eval_set_name: str
    eval_set_path: str
    capability_name: str
    case_id: str
    case_count: int


def upsert_regression_case(request: RegressionCaseRequest) -> RegressionCaseSummary:
    existing = _load_existing_eval_set(request)
    case = EvalCase(
        id=request.case_id,
        input=tuple(_parse_input(value) for value in request.inputs),
        expected_checks=(
            *(
                EvalExpectedCheck(name=check, flaky=False)
                for check in request.expected_checks
            ),
            *(
                EvalExpectedCheck(name=check, flaky=True)
                for check in request.flaky_checks
            ),
        ),
        harness_commands=request.harness_commands,
    )
    cases = tuple(
        existing_case for existing_case in existing.cases if existing_case.id != case.id
    )
    eval_set = existing.model_copy(update={"cases": (*cases, case)})
    eval_set_path = write_eval_set(eval_set, request.eval_set_dir)
    return RegressionCaseSummary(
        eval_set_name=eval_set.name,
        eval_set_path=str(eval_set_path),
        capability_name=eval_set.capability_name,
        case_id=case.id,
        case_count=len(eval_set.cases),
    )


def _load_existing_eval_set(request: RegressionCaseRequest) -> EvalSet:
    try:
        return load_eval_set(request.eval_set_name, request.eval_set_dir)
    except ArtifactNotFoundError:
        return EvalSet(
            name=request.eval_set_name,
            version=request.eval_set_version,
            capability_name=request.capability_name,
        )


def _parse_input(value: str) -> EvalCaseInput:
    key, separator, item_value = value.partition("=")
    if not separator or not key or not item_value:
        raise EvalCaseInputParseError(value=value)
    return EvalCaseInput(name=key, value=item_value)
