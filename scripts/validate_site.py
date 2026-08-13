#!/usr/bin/env python3
"""Validate the staged static site before it is published."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


ARTIFACT_BUDGET = 50 * 1024 * 1024
FILE_BUDGET = 20 * 1024 * 1024


def validate(dist: Path) -> None:
    index = dist / "index.html"
    if not index.is_file():
        raise SystemExit(f"Missing site entry point: {index}")
    if not (dist / ".nojekyll").is_file():
        raise SystemExit("Missing dist/.nojekyll")

    files = [path for path in dist.rglob("*") if path.is_file()]
    total = sum(path.stat().st_size for path in files)
    if total > ARTIFACT_BUDGET:
        raise SystemExit(
            f"Site is {total / 1024 / 1024:.1f} MB; budget is 50 MB"
        )
    oversized = [path for path in files if path.stat().st_size > FILE_BUDGET]
    if oversized:
        raise SystemExit(f"Unexpected files above 20 MB: {oversized}")

    html = index.read_text(encoding="utf-8")
    references = set(re.findall(r"data/web/[A-Za-z0-9_.-]+", html))
    missing = sorted(reference for reference in references if not (dist / reference).is_file())
    if missing:
        raise SystemExit(f"Missing referenced web assets: {missing}")

    for path in (dist / "data" / "web").glob("*.geojson"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("type") != "FeatureCollection" or not isinstance(
            payload.get("features"), list
        ):
            raise SystemExit(f"Malformed GeoJSON FeatureCollection: {path}")

    forbidden = ("file://", "localhost", "Non-SPPE", "verification in progress")
    for value in forbidden:
        if value in html:
            raise SystemExit(f"Generated HTML contains forbidden text: {value}")
    required = (
        "California Energy Commission SPPE dockets",
        "Spatial proximity does not establish causation",
        "not treated as zero",
        "https://www.energy.ca.gov/",
    )
    missing_copy = [value for value in required if value not in html]
    if missing_copy:
        raise SystemExit(f"Required sources or caveats are missing: {missing_copy}")

    print(
        f"Validated {len(files)} files, {len(references)} referenced assets, "
        f"{total / 1024 / 1024:.1f} MB total"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("dist", nargs="?", type=Path, default=Path("dist"))
    arguments = parser.parse_args()
    validate(arguments.dist.resolve())


if __name__ == "__main__":
    main()
