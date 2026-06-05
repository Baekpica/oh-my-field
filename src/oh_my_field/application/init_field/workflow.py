from pathlib import Path

import yaml

from oh_my_field.domain.layout import (
    DEFAULT_CACHE_DIR,
    DEFAULT_CAPABILITIES_DIR,
    DEFAULT_CONTEXT_DIR,
    DEFAULT_DATASETS_DIR,
    DEFAULT_EVAL_DIR,
    DEFAULT_EVIDENCE_DIR,
    DEFAULT_EXPORTS_DIR,
    DEFAULT_IMPORTS_DIR,
    DEFAULT_LEARNING_DIR,
    DEFAULT_REFLECTIONS_DIR,
    DEFAULT_REPLAYS_DIR,
    DEFAULT_RUNS_DIR,
    DEFAULT_WORKFLOWS_DIR,
    OMF_DIR,
)
from oh_my_field.models import StrictModel

FIELD_CONFIG_SCHEMA_VERSION = "omf.field_config.v0.1"
REGISTRY_SCHEMA_VERSION = "omf.registry.v0.1"
DEFAULT_OMFIGNORE_PATTERNS: tuple[str, ...] = (
    ".git/",
    ".venv/",
    "node_modules/",
    "dist/",
    "build/",
    ".env*",
    "*.pem",
    "*.key",
    "*.sqlite",
    "*.db",
    "*.zip",
    "*.tar.gz",
)


class InitFieldRequest(StrictModel):
    root: Path = Path()
    runtime: str = "codex"
    model: str | None = None
    capabilities_dir: Path = DEFAULT_CAPABILITIES_DIR


class InitFieldSummary(StrictModel):
    root: str
    config_path: str
    registry_path: str
    omfignore_path: str
    created_directories: tuple[str, ...]
    existing_directories: tuple[str, ...]
    created_files: tuple[str, ...]
    existing_files: tuple[str, ...]


def initialize_field(request: InitFieldRequest) -> InitFieldSummary:
    root = request.root.resolve()
    omf_dir = root / OMF_DIR
    directories = (
        omf_dir,
        _resolve_layout_path(root, DEFAULT_EVIDENCE_DIR),
        _resolve_layout_path(root, request.capabilities_dir),
        _resolve_layout_path(root, DEFAULT_EXPORTS_DIR),
        _resolve_layout_path(root, DEFAULT_IMPORTS_DIR),
        _resolve_layout_path(root, DEFAULT_RUNS_DIR),
        _resolve_layout_path(root, DEFAULT_CACHE_DIR),
        _resolve_layout_path(root, DEFAULT_EVAL_DIR),
        _resolve_layout_path(root, DEFAULT_REPLAYS_DIR),
        _resolve_layout_path(root, DEFAULT_CONTEXT_DIR),
        _resolve_layout_path(root, DEFAULT_LEARNING_DIR),
        _resolve_layout_path(root, DEFAULT_DATASETS_DIR),
        _resolve_layout_path(root, DEFAULT_REFLECTIONS_DIR),
        _resolve_layout_path(root, DEFAULT_WORKFLOWS_DIR),
    )
    created_directories, existing_directories = _ensure_directories(directories)

    config_path = omf_dir / "config.yaml"
    registry_path = omf_dir / "registry.yaml"
    omfignore_path = root / ".omfignore"
    created_files: list[Path] = []
    existing_files: list[Path] = []

    _write_yaml_if_missing(
        config_path,
        _config_payload(request),
        created=created_files,
        existing=existing_files,
    )
    _write_yaml_if_missing(
        registry_path,
        {"schema_version": REGISTRY_SCHEMA_VERSION, "capabilities": []},
        created=created_files,
        existing=existing_files,
    )
    _write_text_if_missing(
        omfignore_path,
        "\n".join(DEFAULT_OMFIGNORE_PATTERNS) + "\n",
        created=created_files,
        existing=existing_files,
    )

    return InitFieldSummary(
        root=str(root),
        config_path=str(config_path),
        registry_path=str(registry_path),
        omfignore_path=str(omfignore_path),
        created_directories=_relative_paths(root, created_directories),
        existing_directories=_relative_paths(root, existing_directories),
        created_files=_relative_paths(root, tuple(created_files)),
        existing_files=_relative_paths(root, tuple(existing_files)),
    )


def _config_payload(request: InitFieldRequest) -> dict[str, object]:
    return {
        "schema_version": FIELD_CONFIG_SCHEMA_VERSION,
        "default_runtime": {
            "runtime": request.runtime,
            "model": request.model,
        },
        "storage": {
            "evidence_dir": DEFAULT_EVIDENCE_DIR.as_posix(),
            "capabilities_dir": request.capabilities_dir.as_posix(),
            "exports_dir": DEFAULT_EXPORTS_DIR.as_posix(),
            "imports_dir": DEFAULT_IMPORTS_DIR.as_posix(),
            "runs_dir": DEFAULT_RUNS_DIR.as_posix(),
            "cache_dir": DEFAULT_CACHE_DIR.as_posix(),
        },
        "artifact_policy": {
            "ignore_file": ".omfignore",
            "default_excludes": list(DEFAULT_OMFIGNORE_PATTERNS),
        },
    }


def _ensure_directories(
    directories: tuple[Path, ...],
) -> tuple[tuple[Path, ...], tuple[Path, ...]]:
    created: list[Path] = []
    existing: list[Path] = []
    for directory in directories:
        if directory.exists():
            existing.append(directory)
            continue
        directory.mkdir(parents=True)
        created.append(directory)
    return tuple(created), tuple(existing)


def _write_yaml_if_missing(
    path: Path,
    payload: dict[str, object],
    *,
    created: list[Path],
    existing: list[Path],
) -> None:
    text = yaml.safe_dump(payload, sort_keys=False)
    _write_text_if_missing(path, text, created=created, existing=existing)


def _write_text_if_missing(
    path: Path,
    text: str,
    *,
    created: list[Path],
    existing: list[Path],
) -> None:
    if path.exists():
        existing.append(path)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    created.append(path)


def _resolve_layout_path(root: Path, path: Path) -> Path:
    if path.is_absolute():
        return path
    return root / path


def _relative_paths(root: Path, paths: tuple[Path, ...]) -> tuple[str, ...]:
    return tuple(_relative_path(root, path) for path in paths)


def _relative_path(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)
