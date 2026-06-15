import os
import platform
import shutil
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import cast

import yaml

from oh_my_field import __version__
from oh_my_field.domain.layout import (
    DEFAULT_CAPABILITIES_DIR,
    OMF_DIR,
)
from oh_my_field.models import StrictModel

SCHEMA_VERSIONS = {
    "capability": "0.1",
    "evidence": "0.1",
    "harness": "0.1",
    "portability": "0.2",
}
OPTIONAL_RUNTIME_COMMANDS = ("codex", "claude", "hermes-code")


class VersionSummary(StrictModel):
    version: str
    python: str
    platform: str
    schema_versions: dict[str, str]


class DoctorSummary(StrictModel):
    version: str
    executable: str | None
    python: str
    platform: str
    cwd: str
    field_config_found: bool
    configured_capabilities_dir: str | None
    canonical_capabilities_dir: str
    layout_warnings: tuple[str, ...]
    cwd_writable: bool
    omf_dir_creatable: bool
    git: bool
    uv: bool
    pipx: bool
    optional_runtimes: dict[str, bool]


def build_version_summary() -> VersionSummary:
    return VersionSummary(
        version=__version__,
        python=platform.python_version(),
        platform=platform.platform(),
        schema_versions=SCHEMA_VERSIONS,
    )


def render_version_text(summary: VersionSummary) -> str:
    schemas = ", ".join(
        f"{name}={version}" for name, version in summary.schema_versions.items()
    )
    return (
        f"oh-my-field {summary.version}\n"
        f"Python {summary.python}\n"
        f"Platform {summary.platform}\n"
        f"Schemas {schemas}"
    )


def build_doctor_summary(cwd: Path | None = None) -> DoctorSummary:
    current_dir = (cwd or Path.cwd()).resolve()
    config_path = current_dir / OMF_DIR / "config.yaml"
    configured_capabilities_dir = _configured_capabilities_dir(config_path)
    return DoctorSummary(
        version=__version__,
        executable=shutil.which("omf"),
        python=sys.executable,
        platform=platform.platform(),
        cwd=str(current_dir),
        field_config_found=config_path.exists(),
        configured_capabilities_dir=configured_capabilities_dir,
        canonical_capabilities_dir=DEFAULT_CAPABILITIES_DIR.as_posix(),
        layout_warnings=_layout_warnings(configured_capabilities_dir),
        cwd_writable=os.access(current_dir, os.W_OK),
        omf_dir_creatable=_omf_dir_creatable(current_dir),
        git=shutil.which("git") is not None,
        uv=shutil.which("uv") is not None,
        pipx=shutil.which("pipx") is not None,
        optional_runtimes={
            command: shutil.which(command) is not None
            for command in OPTIONAL_RUNTIME_COMMANDS
        },
    )


def render_doctor_text(summary: DoctorSummary) -> str:
    runtime_lines = "\n".join(
        f"optional runtime {command}: {_status(installed)}"
        for command, installed in summary.optional_runtimes.items()
    )
    layout_lines = [
        f"field config: {_status(summary.field_config_found)}",
        f"canonical capabilities dir: {summary.canonical_capabilities_dir}",
    ]
    if summary.configured_capabilities_dir is not None:
        layout_lines.append(
            f"configured capabilities dir: {summary.configured_capabilities_dir}",
        )
    layout_lines.extend(
        f"layout warning: {warning}" for warning in summary.layout_warnings
    )
    return "\n".join(
        (
            f"oh-my-field {summary.version}",
            f"executable: {summary.executable or 'not found on PATH'}",
            f"python: {summary.python}",
            f"platform: {summary.platform}",
            f"cwd: {summary.cwd}",
            *layout_lines,
            f"cwd writable: {_status(summary.cwd_writable)}",
            f".omf creatable: {_status(summary.omf_dir_creatable)}",
            f"git: {_status(summary.git)}",
            f"uv: {_status(summary.uv)}",
            f"pipx: {_status(summary.pipx)}",
            runtime_lines,
        ),
    )


def _omf_dir_creatable(cwd: Path) -> bool:
    omf_dir = cwd / OMF_DIR
    if omf_dir.exists():
        return omf_dir.is_dir() and os.access(omf_dir, os.W_OK)
    return os.access(cwd, os.W_OK)


def _configured_capabilities_dir(config_path: Path) -> str | None:
    if not config_path.exists():
        return None
    loaded: object = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(loaded, Mapping):
        return None
    config = cast("Mapping[str, object]", loaded)
    storage = config.get("storage")
    if not isinstance(storage, Mapping):
        return None
    storage_config = cast("Mapping[str, object]", storage)
    capabilities_dir = storage_config.get("capabilities_dir")
    if not isinstance(capabilities_dir, str) or not capabilities_dir:
        return None
    return capabilities_dir


def _layout_warnings(configured_capabilities_dir: str | None) -> tuple[str, ...]:
    if configured_capabilities_dir is None:
        return ()
    canonical = DEFAULT_CAPABILITIES_DIR.as_posix()
    if configured_capabilities_dir == canonical:
        return ()
    return (
        "configured capabilities_dir points to "
        f"{configured_capabilities_dir}; canonical release layout is {canonical}/",
    )


def _status(value: bool) -> str:
    return "ok" if value else "missing"
