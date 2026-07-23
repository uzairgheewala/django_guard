#!/usr/bin/env python
"""Generate or verify PlanGuard's JSON Schema and TypeScript contracts."""

from __future__ import annotations

import argparse
import filecmp
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "planguard-core" / "src"))

from planguard.contracts.generate import generate_contracts  # noqa: E402


def _snapshot(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Verify committed contracts are current without rewriting them")
    args = parser.parse_args()

    schema_dir = ROOT / "schemas" / "generated"
    typescript_path = ROOT / "apps" / "workbench-ui" / "src" / "generated" / "artifact-types.ts"
    if not args.check:
        generate_contracts(schema_dir, typescript_path)
        return 0

    with tempfile.TemporaryDirectory(prefix="planguard-contracts-") as temp:
        temp_root = Path(temp)
        generated_schema_dir = temp_root / "schemas"
        generated_typescript = temp_root / "artifact-types.ts"
        generate_contracts(generated_schema_dir, generated_typescript)
        expected_schemas = _snapshot(schema_dir)
        actual_schemas = _snapshot(generated_schema_dir)
        failures: list[str] = []
        if expected_schemas != actual_schemas:
            missing = sorted(set(actual_schemas) - set(expected_schemas))
            stale = sorted(set(expected_schemas) - set(actual_schemas))
            changed = sorted(
                key for key in set(expected_schemas) & set(actual_schemas)
                if expected_schemas[key] != actual_schemas[key]
            )
            failures.append(f"schemas missing={missing} stale={stale} changed={changed}")
        if not typescript_path.exists() or not filecmp.cmp(typescript_path, generated_typescript, shallow=False):
            failures.append("TypeScript artifact contract is stale")
        if failures:
            print("Contract verification failed:")
            for failure in failures:
                print(f"- {failure}")
            return 1
    print("Contract verification passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
