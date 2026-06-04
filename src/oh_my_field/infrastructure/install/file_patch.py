from dataclasses import dataclass
from importlib.resources.abc import Traversable
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ResourceText:
    source: str
    content: str


def read_resource_text(resource: Traversable) -> ResourceText:
    return ResourceText(
        source=str(resource),
        content=resource.read_text(encoding="utf-8"),
    )


def write_text_if_allowed(
    *,
    target_path: Path,
    content: str,
    overwrite: bool,
    dry_run: bool,
) -> bool:
    if dry_run:
        return False
    if target_path.exists() and not overwrite:
        return False
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(content, encoding="utf-8")
    return True
