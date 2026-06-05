from importlib.resources.abc import Traversable
from pathlib import Path


def resource_at(root: Traversable, relative_path: Path) -> Traversable:
    resource = root
    for part in relative_path.parts:
        resource = resource.joinpath(part)
    return resource
