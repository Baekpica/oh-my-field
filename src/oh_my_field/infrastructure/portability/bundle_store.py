import hashlib
import tarfile
from pathlib import Path, PurePosixPath

import yaml

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


def package_archive_path(out: Path) -> Path:
    if _is_archive_path(out):
        return out
    return out.with_name(f"{out.name}.omfcap.tar.gz")


def package_staging_dir(out: Path) -> Path:
    if out.name.endswith(".omfcap.tar.gz"):
        return out.with_name(out.name[: -len(".omfcap.tar.gz")])
    if out.name.endswith(".tar.gz"):
        return out.with_name(out.name[: -len(".tar.gz")])
    if out.suffix == ".tgz":
        return out.with_suffix("")
    return out


def write_package_metadata(
    bundle_path: Path,
    portability: PortabilityManifest,
) -> None:
    write_text_exclusive(
        bundle_path / "package.yaml",
        yaml.safe_dump(
            {
                "schema_version": "omf.package.v0.1",
                "package_format": "omfcap.tar.gz",
                "capability": portability.capability,
                "version": portability.version,
                "target": portability.target.model_dump(mode="json"),
                "canonical_import": (
                    "omf capability import <package.omfcap.tar.gz> "
                    f"--runtime {portability.target.runtime} --validate"
                ),
            },
            sort_keys=False,
        ),
    )
    manifest = _hash_manifest(bundle_path)
    write_text_exclusive(bundle_path / "MANIFEST.sha256", manifest)


def create_archive(bundle_path: Path, archive_path: Path) -> Path:
    if archive_path.exists():
        raise PortabilityBundleExistsError(path=archive_path)
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive_path, "w:gz") as archive:
        for path in sorted(bundle_path.rglob("*")):
            arcname = path.relative_to(bundle_path).as_posix()
            info = archive.gettarinfo(str(path), arcname=arcname)
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            info.mtime = 0
            if path.is_file():
                with path.open("rb") as handle:
                    archive.addfile(info, handle)
            else:
                archive.addfile(info)
    return archive_path


def prepare_bundle_for_import(
    bundle_path: Path,
    import_dir: Path,
) -> tuple[Path, Path | None]:
    if bundle_path.is_dir():
        return bundle_path, None
    if not _is_archive_path(bundle_path):
        return bundle_path, None
    unpacked = _unpack_archive(bundle_path, import_dir)
    return unpacked, unpacked


def verify_package_manifest(bundle_path: Path) -> tuple[bool, tuple[str, ...]]:
    if bundle_path.is_dir():
        return _verify_directory_manifest(bundle_path)
    if _is_archive_path(bundle_path):
        return _verify_archive_manifest(bundle_path)
    return False, (f"not an OMF capability package archive: {bundle_path}",)


def write_export_bundle(
    bundle_path: Path,
    manifest: CapabilityManifest,
    portability: PortabilityManifest,
) -> None:
    from oh_my_field.application.portability.rendering import (  # noqa: PLC0415
        base_instructions,
        bundle_readme,
        compact_instructions,
        compressed_context_pack,
        model_notes,
        model_notes_file,
        yaml_dump,
    )

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


def _is_archive_path(path: Path) -> bool:
    return path.name.endswith((".omfcap.tar.gz", ".tar.gz")) or path.suffix == ".tgz"


def _hash_manifest(bundle_path: Path) -> str:
    lines: list[str] = []
    for path in sorted(bundle_path.rglob("*")):
        if not path.is_file() or path.name == "MANIFEST.sha256":
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{digest}  {path.relative_to(bundle_path).as_posix()}")
    return "\n".join(lines) + ("\n" if lines else "")


def _verify_directory_manifest(bundle_path: Path) -> tuple[bool, tuple[str, ...]]:
    manifest_path = bundle_path / "MANIFEST.sha256"
    if not manifest_path.exists():
        return False, ("MANIFEST.sha256 not found",)
    errors: list[str] = []
    for line in manifest_path.read_text(encoding="utf-8").splitlines():
        expected, separator, relative = line.partition("  ")
        if not separator:
            errors.append(f"invalid manifest line: {line}")
            continue
        path = bundle_path / relative
        if not path.is_file():
            errors.append(f"manifest file missing: {relative}")
            continue
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            errors.append(f"manifest hash mismatch: {relative}")
    return not errors, tuple(errors)


def _verify_archive_manifest(  # noqa: C901
    archive_path: Path,
) -> tuple[bool, tuple[str, ...]]:
    errors: list[str] = []
    files: dict[str, bytes] = {}
    try:
        with tarfile.open(archive_path, "r:gz") as archive:
            for member in archive.getmembers():
                safety_error = _unsafe_member_reason(member)
                if safety_error is not None:
                    errors.append(safety_error)
                    continue
                if not member.isfile():
                    continue
                extracted = archive.extractfile(member)
                if extracted is None:
                    errors.append(f"could not read archive member: {member.name}")
                    continue
                files[member.name] = extracted.read()
    except (OSError, tarfile.TarError) as exc:
        return False, (str(exc),)
    manifest_bytes = files.get("MANIFEST.sha256")
    if manifest_bytes is None:
        errors.append("MANIFEST.sha256 not found")
        return False, tuple(errors)
    for line in manifest_bytes.decode("utf-8").splitlines():
        expected, separator, relative = line.partition("  ")
        if not separator:
            errors.append(f"invalid manifest line: {line}")
            continue
        content = files.get(relative)
        if content is None:
            errors.append(f"manifest file missing: {relative}")
            continue
        actual = hashlib.sha256(content).hexdigest()
        if actual != expected:
            errors.append(f"manifest hash mismatch: {relative}")
    return not errors, tuple(errors)


def _unpack_archive(archive_path: Path, import_dir: Path) -> Path:
    if not archive_path.exists():
        raise PortabilityBundleParseError(path=archive_path, reason="archive not found")
    destination = _unique_unpack_dir(import_dir, _archive_stem(archive_path))
    destination.mkdir(parents=True)
    try:
        with tarfile.open(archive_path, "r:gz") as archive:
            members = archive.getmembers()
            for member in members:
                reason = _unsafe_member_reason(member)
                if reason is not None:
                    raise PortabilityBundleParseError(
                        path=archive_path,
                        reason=reason,
                    )
            # All paths and member types are validated above before extraction.
            archive.extractall(destination, members=members)  # noqa: S202
    except (OSError, tarfile.TarError) as exc:
        raise PortabilityBundleParseError(path=archive_path, reason=str(exc)) from exc
    ok, errors = _verify_directory_manifest(destination)
    if not ok:
        raise PortabilityBundleParseError(
            path=archive_path,
            reason="; ".join(errors),
        )
    return destination


def _unsafe_member_reason(member: tarfile.TarInfo) -> str | None:
    name = member.name
    path = PurePosixPath(name)
    if not name or path.is_absolute():
        return f"unsafe archive member path: {name}"
    if any(part in ("", ".", "..") for part in path.parts):
        return f"unsafe archive member path: {name}"
    if member.issym() or member.islnk():
        return f"archive links are not allowed: {name}"
    if not (member.isdir() or member.isfile()):
        return f"unsupported archive member type: {name}"
    return None


def _archive_stem(path: Path) -> str:
    if path.name.endswith(".omfcap.tar.gz"):
        return path.name[: -len(".omfcap.tar.gz")]
    if path.name.endswith(".tar.gz"):
        return path.name[: -len(".tar.gz")]
    if path.suffix == ".tgz":
        return path.stem
    return path.name


def _unique_unpack_dir(import_dir: Path, stem: str) -> Path:
    candidate = import_dir / stem
    index = 2
    while candidate.exists():
        candidate = import_dir / f"{stem}_{index}"
        index += 1
    return candidate


def write_text_exclusive(target_path: Path, content: str) -> None:
    write_text(target_path, content, overwrite=False)


def write_text(target_path: Path, content: str, *, overwrite: bool) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    if target_path.exists() and not overwrite:
        raise DuplicateWriteError(path=target_path)
    target_path.write_text(content, encoding="utf-8")
