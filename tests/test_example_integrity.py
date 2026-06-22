from pathlib import Path

import pytest

from oh_my_field.integrity import model_sha256
from oh_my_field.storage import load_manifest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    ("capabilities_dir", "capability_name"),
    [
        (
            ROOT / "examples" / "10min-happy-path" / "capabilities",
            "csv_normalize",
        ),
        (
            ROOT / "examples" / "10min-codex-backtest" / "capabilities",
            "portfolio_backtest",
        ),
    ],
)
def test_committed_example_capability_integrity_is_current(
    capabilities_dir: Path,
    capability_name: str,
) -> None:
    manifest = load_manifest(capability_name, capabilities_dir)

    assert manifest.integrity_chain[-1].sha256 == model_sha256(manifest)
