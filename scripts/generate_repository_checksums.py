#!/usr/bin/env python3
"""Generate a deterministic SHA-256 inventory for the canonical repository tree."""

from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "SHA256SUMS"
EXCLUDED_PARTS = {
    ".git",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
}
EXCLUDED_NAMES = {
    "SHA256SUMS",
    "registry.sqlite3",
    "DELTA_MANIFEST.json",
    "DELTA_FILE_SHA256SUMS",
}


def included(path: Path) -> bool:
    relative = path.relative_to(ROOT)
    return path.is_file() and not (set(relative.parts) & EXCLUDED_PARTS) and path.name not in EXCLUDED_NAMES


def main() -> int:
    lines: list[str] = []
    for path in sorted((item for item in ROOT.rglob("*") if included(item)), key=lambda item: item.as_posix()):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{digest}  {path.relative_to(ROOT).as_posix()}")
    OUTPUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {len(lines)} checksums to {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
