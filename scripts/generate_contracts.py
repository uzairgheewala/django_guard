#!/usr/bin/env python
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "planguard-core" / "src"))

from planguard.contracts.generate import generate_contracts  # noqa: E402


def main() -> None:
    generate_contracts(
        ROOT / "schemas" / "generated",
        ROOT / "apps" / "workbench-ui" / "src" / "generated" / "artifact-types.ts",
    )


if __name__ == "__main__":
    main()
