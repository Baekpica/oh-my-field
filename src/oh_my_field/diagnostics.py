import os
import platform
import shutil
import sys
from pathlib import Path

from oh_my_field import __version__
from oh_my_field.models import StrictModel

SCHEMA_VERSIONS = {
    "capability": "0.1",
    "evidence": "0.1",
    "portability": "0.1",
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
    return DoctorSummary(
        version=__version__,
        executable=shutil.which("omf"),
        python=sys.executable,
        platform=platform.platform(),
        cwd=str(current_dir),
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
    return "\n".join(
        (
            f"oh-my-field {summary.version}",
            f"executable: {summary.executable or 'not found on PATH'}",
            f"python: {summary.python}",
            f"platform: {summary.platform}",
            f"cwd: {summary.cwd}",
            f"cwd writable: {_status(summary.cwd_writable)}",
            f".omf creatable: {_status(summary.omf_dir_creatable)}",
            f"git: {_status(summary.git)}",
            f"uv: {_status(summary.uv)}",
            f"pipx: {_status(summary.pipx)}",
            runtime_lines,
        ),
    )


def _omf_dir_creatable(cwd: Path) -> bool:
    omf_dir = cwd / ".omf"
    if omf_dir.exists():
        return omf_dir.is_dir() and os.access(omf_dir, os.W_OK)
    return os.access(cwd, os.W_OK)


def _status(value: bool) -> str:
    return "ok" if value else "missing"
