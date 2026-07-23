from __future__ import annotations

from pathlib import Path

from planguard.contracts.generate import generate_contracts


ROOT = Path(__file__).resolve().parents[2]


def test_committed_contracts_are_reproducible(tmp_path) -> None:
    schema_dir = tmp_path / "schemas"
    typescript = tmp_path / "artifact-types.ts"
    generate_contracts(schema_dir, typescript)

    committed_schema_dir = ROOT / "schemas" / "generated"
    for generated in schema_dir.glob("*.json"):
        assert generated.read_bytes() == (committed_schema_dir / generated.name).read_bytes()

    assert typescript.read_bytes() == (
        ROOT / "apps" / "workbench-ui" / "src" / "generated" / "artifact-types.ts"
    ).read_bytes()
