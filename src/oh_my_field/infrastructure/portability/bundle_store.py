from pathlib import Path

import yaml

from oh_my_field.application.portability.rendering import (
    base_instructions,
    bundle_readme,
    compact_instructions,
    compressed_context_pack,
    model_notes,
    model_notes_file,
    yaml_dump,
)
from oh_my_field.contract_rendering import (
    artifact_contracts_yaml,
    replay_plan_yaml,
    task_contract_yaml,
    validation_markdown,
    validator_script,
)
from oh_my_field.domain.models import CapabilityManifest
from oh_my_field.domain.portability.errors import (
    PortabilityBundleExistsError,
    PortabilityBundleParseError,
)
from oh_my_field.domain.portability.models import PortabilityManifest
from oh_my_field.domain.portability.readiness import model_downgrade
from oh_my_field.infrastructure.fs.storage import DuplicateWriteError


def ensure_new_directory(path: Path) -> None:
    if path.exists():
        raise PortabilityBundleExistsError(path=path)
    path.mkdir(parents=True)


def write_export_bundle(
    bundle_path: Path,
    manifest: CapabilityManifest,
    portability: PortabilityManifest,
) -> None:
    write_text_exclusive(bundle_path / "capability.yaml", yaml_dump(manifest))
    write_text_exclusive(bundle_path / "portability.yaml", yaml_dump(portability))
    write_text_exclusive(bundle_path / "README.md", bundle_readme(portability))
    write_text_exclusive(
        bundle_path / "instructions" / "base.md",
        base_instructions(manifest),
    )
    if model_downgrade(portability):
        write_text_exclusive(
            bundle_path / "instructions" / "compact.md",
            compact_instructions(manifest),
        )
        write_text_exclusive(
            bundle_path / "instructions" / model_notes_file(portability),
            model_notes(portability),
        )
    write_text_exclusive(
        bundle_path / "context" / "context.policy.yaml",
        yaml_dump(manifest.context),
    )
    if portability.compatibility.compression_required:
        write_text_exclusive(
            bundle_path / "context" / "context.pack.md",
            compressed_context_pack(manifest, portability),
        )
        write_text_exclusive(
            bundle_path / "context" / "forbidden.yaml",
            yaml.safe_dump(
                {"forbidden": list(manifest.context.forbidden)},
                sort_keys=False,
            ),
        )
    write_text_exclusive(
        bundle_path / "harness" / "harness.yaml",
        yaml_dump(manifest.harness),
    )
    _write_contract_bundle(bundle_path, manifest)
    write_text_exclusive(
        bundle_path / "provenance" / "source_runtime.yaml",
        yaml_dump(portability.source),
    )
    write_text_exclusive(
        bundle_path / "provenance" / "evidence_links.yaml",
        yaml.safe_dump(
            {"evidence_ids": list(portability.source.evidence_ids)},
            sort_keys=False,
        ),
    )


def _write_contract_bundle(bundle_path: Path, manifest: CapabilityManifest) -> None:
    write_text_exclusive(
        bundle_path / "contracts" / "task_contract.yaml",
        task_contract_yaml(manifest),
    )
    write_text_exclusive(
        bundle_path / "contracts" / "artifacts.yaml",
        artifact_contracts_yaml(manifest),
    )
    write_text_exclusive(
        bundle_path / "contracts" / "validation.md",
        validation_markdown(manifest),
    )
    write_text_exclusive(
        bundle_path / "contracts" / "replay_plan.yaml",
        replay_plan_yaml(manifest),
    )
    write_text_exclusive(
        bundle_path / "validators" / "validate_contract.py",
        validator_script(manifest),
    )


def load_bundle(bundle_path: Path) -> tuple[CapabilityManifest, PortabilityManifest]:
    try:
        capability_yaml = bundle_path.joinpath("capability.yaml").read_text(
            encoding="utf-8",
        )
        portability_yaml = bundle_path.joinpath("portability.yaml").read_text(
            encoding="utf-8",
        )
    except OSError as exc:
        raise PortabilityBundleParseError(path=bundle_path, reason=str(exc)) from exc
    try:
        capability_data = yaml.safe_load(capability_yaml)
        portability_data = yaml.safe_load(portability_yaml)
        manifest = CapabilityManifest.model_validate(capability_data)
        portability = PortabilityManifest.model_validate(portability_data)
    except (yaml.YAMLError, ValueError) as exc:
        raise PortabilityBundleParseError(path=bundle_path, reason=str(exc)) from exc
    return manifest, portability


def write_text_exclusive(target_path: Path, content: str) -> None:
    write_text(target_path, content, overwrite=False)


def write_text(target_path: Path, content: str, *, overwrite: bool) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    if target_path.exists() and not overwrite:
        raise DuplicateWriteError(path=target_path)
    target_path.write_text(content, encoding="utf-8")
