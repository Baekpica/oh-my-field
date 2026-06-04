import json
from dataclasses import dataclass
from difflib import unified_diff
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from oh_my_field.models import StrictModel
from oh_my_field.storage import (
    capability_package_paths,
    load_evidence,
    load_learning_patch_decision,
)

type DiffTargetType = Literal["evidence", "capability", "harness", "learning-patch"]


class DiffError(Exception):
    pass


@dataclass
class DiffInputError(DiffError):
    reason: str

    def __str__(self) -> str:
        return self.reason


@dataclass
class DiffReadError(DiffError):
    path: Path
    reason: str

    def __str__(self) -> str:
        return f"could not read diff input {self.path}: {self.reason}"


class DiffRequest(StrictModel):
    target_type: DiffTargetType
    left: str
    right: str | None = None
    capabilities_dir: Path = Path("capabilities")
    from_capabilities_dir: Path | None = None
    to_capabilities_dir: Path | None = None
    evidence_dir: Path = Path(".omf/evidence")
    learning_patch_dir: Path = Path(".omf/learning_patches")


class DiffSummary(StrictModel):
    target_type: DiffTargetType
    left: str
    right: str
    changed: bool
    diff_text: str


def compare_artifacts(request: DiffRequest) -> DiffSummary:
    if request.target_type == "evidence":
        left, right = _evidence_inputs(request)
    elif request.target_type == "capability":
        left, right = _capability_inputs(request)
    elif request.target_type == "harness":
        left, right = _harness_inputs(request)
    else:
        left, right = _learning_patch_inputs(request)
    diff_text = "".join(
        unified_diff(
            left.lines,
            right.lines,
            fromfile=left.label,
            tofile=right.label,
        ),
    )
    return DiffSummary(
        target_type=request.target_type,
        left=left.label,
        right=right.label,
        changed=bool(diff_text),
        diff_text=diff_text,
    )


@dataclass(frozen=True, slots=True)
class _DiffInput:
    label: str
    lines: list[str]


def _evidence_inputs(request: DiffRequest) -> tuple[_DiffInput, _DiffInput]:
    right = _required_right(request)
    return (
        _model_input(
            label=f"evidence/{request.left}.json",
            model=load_evidence(request.left, request.evidence_dir),
        ),
        _model_input(
            label=f"evidence/{right}.json",
            model=load_evidence(right, request.evidence_dir),
        ),
    )


def _capability_inputs(request: DiffRequest) -> tuple[_DiffInput, _DiffInput]:
    left_path, right_path = _capability_paths(request, "capability")
    return _file_input(left_path), _file_input(right_path)


def _harness_inputs(request: DiffRequest) -> tuple[_DiffInput, _DiffInput]:
    left_path, right_path = _capability_paths(request, "harness")
    return _file_input(left_path), _file_input(right_path)


def _learning_patch_inputs(request: DiffRequest) -> tuple[_DiffInput, _DiffInput]:
    right = _required_right(request)
    return (
        _model_input(
            label=f"learning_patches/{request.left}.json",
            model=load_learning_patch_decision(
                request.left,
                request.learning_patch_dir,
            ),
        ),
        _model_input(
            label=f"learning_patches/{right}.json",
            model=load_learning_patch_decision(right, request.learning_patch_dir),
        ),
    )


def _capability_paths(
    request: DiffRequest,
    artifact: Literal["capability", "harness"],
) -> tuple[Path, Path]:
    left_name = request.left
    right_name = request.right or request.left
    left_dir = request.from_capabilities_dir or request.capabilities_dir
    right_dir = request.to_capabilities_dir or request.capabilities_dir
    if left_name == right_name and left_dir == right_dir:
        reason = (
            "capability and harness diff need a second capability name or "
            "--from-capabilities-dir/--to-capabilities-dir"
        )
        raise DiffInputError(reason)
    left_paths = capability_package_paths(left_name, left_dir)
    right_paths = capability_package_paths(right_name, right_dir)
    if artifact == "harness":
        return left_paths.harness_path, right_paths.harness_path
    return left_paths.capability_path, right_paths.capability_path


def _file_input(path: Path) -> _DiffInput:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise DiffReadError(path=path, reason=str(exc)) from exc
    return _DiffInput(label=str(path), lines=text.splitlines(keepends=True))


def _model_input(label: str, model: BaseModel) -> _DiffInput:
    text = json.dumps(model.model_dump(mode="json"), indent=2, sort_keys=True)
    return _DiffInput(label=label, lines=(text + "\n").splitlines(keepends=True))


def _required_right(request: DiffRequest) -> str:
    if request.right is None:
        reason = f"{request.target_type} diff requires a second id"
        raise DiffInputError(reason)
    return request.right
