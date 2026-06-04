import json
from pathlib import Path
from typing import Any, cast

from pydantic import BaseModel

from oh_my_field.domain.models import (
    CapabilityExportBundle,
    CapabilityManifest,
    EvidenceRecord,
    HarnessResult,
)

type JsonSchema = dict[str, Any]

SCHEMA_ROOT = Path(__file__).parents[1] / "schemas"
JSON_SCHEMA_DRAFT = "https://json-schema.org/draft/2020-12/schema"
SCHEMA_MODELS: dict[str, type[BaseModel]] = {
    "capability.schema.json": CapabilityManifest,
    "evidence.schema.json": EvidenceRecord,
    "harness.schema.json": HarnessResult,
    "export_bundle.schema.json": CapabilityExportBundle,
}


def test_committed_schema_files_match_model_contracts() -> None:
    for filename, model in SCHEMA_MODELS.items():
        assert _load_schema(filename) == _expected_schema(model)


def test_schema_files_declare_json_schema_draft() -> None:
    for filename in SCHEMA_MODELS:
        assert _load_schema(filename)["$schema"] == JSON_SCHEMA_DRAFT


def _load_schema(filename: str) -> JsonSchema:
    return cast(
        "JsonSchema",
        json.loads(SCHEMA_ROOT.joinpath(filename).read_text(encoding="utf-8")),
    )


def _expected_schema(model: type[BaseModel]) -> JsonSchema:
    schema = {
        "$schema": JSON_SCHEMA_DRAFT,
        **model.model_json_schema(),
    }
    return cast(
        "JsonSchema",
        json.loads(json.dumps(schema, sort_keys=True)),
    )
