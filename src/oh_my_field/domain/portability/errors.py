from dataclasses import dataclass
from pathlib import Path


class PortabilityError(Exception):
    pass


@dataclass
class PortabilityBundleExistsError(PortabilityError):
    path: Path

    def __str__(self) -> str:
        return f"refusing to overwrite existing portability bundle: {self.path}"


@dataclass
class PortabilityBundleParseError(PortabilityError):
    path: Path
    reason: str

    def __str__(self) -> str:
        return f"could not parse portability bundle {self.path}: {self.reason}"


@dataclass
class PortabilityImportNotFoundError(PortabilityError):
    capability: str
    runtime: str
    model: str | None

    def __str__(self) -> str:
        target = self.runtime if self.model is None else f"{self.runtime}/{self.model}"
        return (
            f"no imported target {target!r} for capability {self.capability!r}; "
            "run `omf capability import` first"
        )


@dataclass
class PortabilityAmbiguousTargetError(PortabilityError):
    capability: str
    runtime: str

    def __str__(self) -> str:
        return (
            f"multiple imported targets for runtime {self.runtime!r} on capability "
            f"{self.capability!r}; pass --model to disambiguate"
        )


@dataclass
class PortabilityImportExistsError(PortabilityError):
    capability: str
    capabilities_dir: Path

    def __str__(self) -> str:
        return (
            f"capability {self.capability!r} already exists in "
            f"{self.capabilities_dir}; pass --if-exists overwrite|version|merge"
        )
