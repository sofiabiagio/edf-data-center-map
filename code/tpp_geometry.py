"""Phase-zero geometry helpers for the 2025-2026 CAISO TPP map.

The source spreadsheet is authoritative for the project rows and endpoints.
This module resolves those endpoints against the complete CEC substation
service and guarantees that every CSV row produces a map geometry.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

import geopandas as gpd
import pandas as pd
import requests
from shapely.geometry import LineString, Point
from shapely.ops import substring, unary_union


SUBSTATION_SERVICE = (
    "https://services1.arcgis.com/ZIL9uO234SBBPGL7/arcgis/rest/services/"
    "CA_Substations_Final/FeatureServer"
)


class EndpointResolutionError(ValueError):
    """Raised when a TPP endpoint cannot be resolved deterministically."""


@dataclass(frozen=True)
class EndpointRule:
    names: tuple[str, ...]
    owner: Optional[str] = None
    county: Optional[str] = None
    voltage: Optional[float] = None
    combine: bool = False


# CAISO and CEC sometimes use different labels for the same facility.
# These are explicit equivalences, not fuzzy matches.
ALIASES = {
    "Mercy Springs SW STA": "Mercy Springs",
    "Los-Esteros": "Los Esteros",
    "San Jose B": "San Jose Station B",
    "San Leandro": "San Leandro U",
    "East Shore": "Eastshore",
}


# A few CEC names are duplicated statewide. The additional filters select the
# facility implied by the CAISO project region, owner, and voltage.
ENDPOINT_RULES = {
    "Walnut": EndpointRule(
        names=("Walnut",),
        county="Stanislaus County",
        voltage=230,
        combine=True,
    ),
    "Lincoln": EndpointRule(
        names=("Lincoln",), owner="PG&E", county="Placer County"
    ),
    "Mariposa": EndpointRule(
        names=("Mariposa",),
        owner="PG&E",
        county="Mariposa County",
        voltage=70,
    ),
    "Metcalf": EndpointRule(
        names=("Metcalf 1", "Metcalf 2"), owner="PG&E", combine=True
    ),
    "Midway": EndpointRule(
        names=("Midway",), owner="PG&E", county="Kern County"
    ),
    "Mesa": EndpointRule(
        names=("Mesa",), owner="SCE", county="Los Angeles County"
    ),
    "Drum": EndpointRule(
        names=("Drum 1", "Drum 2"),
        owner="PG&E",
        county="Placer County",
        voltage=115,
        combine=True,
    ),
    "Imperial Valley": EndpointRule(
        names=("Imperial Valley",), owner="SDG&E", county="Imperial County"
    ),
}


def arcgis_to_gdf(server_url: str, page_size: int = 1000) -> gpd.GeoDataFrame:
    """Download every feature from the first layer of an ArcGIS service.

    ArcGIS GeoJSON responses do not consistently include
    ``exceededTransferLimit``. Pagination therefore continues until a page is
    shorter than the requested page size, and the result is checked against
    the service's count endpoint.
    """

    meta_response = requests.get(server_url, params={"f": "json"}, timeout=60)
    meta_response.raise_for_status()
    meta = meta_response.json()
    if "error" in meta:
        raise RuntimeError(meta["error"])
    if not meta.get("layers"):
        raise RuntimeError(f"ArcGIS service advertises no feature layers: {server_url}")
    layer_id = meta["layers"][0]["id"]
    layer_url = f"{server_url}/{layer_id}"
    layer_meta_response = requests.get(
        layer_url, params={"f": "json"}, timeout=60
    )
    layer_meta_response.raise_for_status()
    layer_meta = layer_meta_response.json()
    oid_field = (
        layer_meta.get("objectIdField")
        or layer_meta.get("objectIdFieldName")
        or next(
            (
                field["name"]
                for field in layer_meta.get("fields", [])
                if field.get("type") == "esriFieldTypeOID"
            ),
            None,
        )
    )
    if not oid_field:
        raise RuntimeError(f"ArcGIS layer advertises no object-ID field: {layer_url}")

    count_response = requests.get(
        f"{layer_url}/query",
        params={"where": "1=1", "returnCountOnly": "true", "f": "json"},
        timeout=60,
    )
    count_response.raise_for_status()
    expected_count = int(count_response.json()["count"])

    features = []
    offset = 0
    while offset < expected_count:
        response = requests.get(
            f"{layer_url}/query",
            params={
                "where": "1=1",
                "outFields": "*",
                "outSR": 4326,
                "f": "geojson",
                "orderByFields": oid_field,
                "resultOffset": offset,
                "resultRecordCount": page_size,
            },
            timeout=120,
        )
        response.raise_for_status()
        try:
            payload = response.json()
        except ValueError as exc:
            raise RuntimeError(
                f"Non-JSON response at offset {offset}: {response.text[:200]}"
            ) from exc
        if "error" in payload:
            raise RuntimeError(payload["error"])
        batch = payload.get("features", [])
        if not batch:
            break
        features.extend(batch)
        offset += len(batch)
        if len(batch) < page_size:
            break

    if len(features) != expected_count:
        raise RuntimeError(
            "Incomplete ArcGIS download: "
            f"received {len(features):,} of {expected_count:,} features"
        )

    frame = gpd.GeoDataFrame.from_features(features, crs="EPSG:4326")
    if oid_field in frame and frame[oid_field].duplicated().any():
        raise RuntimeError("ArcGIS pagination returned duplicate object IDs")
    return frame


def _centroid_for_names(
    substations: gpd.GeoDataFrame, names: Iterable[str]
) -> Point:
    wanted = {name.casefold() for name in names}
    selected = substations[
        substations["Name"].fillna("").astype(str).str.casefold().isin(wanted)
    ]
    if selected.empty:
        raise EndpointResolutionError(
            f"Cannot construct centroid; none of {sorted(wanted)} were found"
        )
    return Point(
        selected.geometry.x.mean(),
        selected.geometry.y.mean(),
    )


def add_phase_zero_reference_points(
    substations: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:
    """Add the three TPP endpoints absent from the CEC point layer.

    DeAnza is an approximate centroid of the surrounding named facilities.
    Mira Sorrento is the mapped substation at 5355 Mira Sorrento Place.
    Trout Canyon is an approximate point at the Yellow Pine/Trout Canyon
    interconnection site near SR-160 and Tecopa Road in Nevada.
    """

    result = substations.copy()
    existing = set(result["Name"].fillna("").astype(str).str.casefold())
    rows = []

    if "deanza" not in existing:
        rows.append(
            {
                "Name": "DeAnza",
                "Owner": "PG&E / SVP coordination",
                "Max_Voltag": 115,
                "COUNTY": "Santa Clara County",
                "CITY": "San Jose area",
                "Status": "Proposed; approximate location",
                "Source": "CAISO TPP; centroid of Newark, Monta Vista, and Nortech",
                "CEC_Sub_ID": "TPP_APPROX_DEANZA",
                "geometry": _centroid_for_names(
                    result, ("Newark", "Monta Vista", "Nortech")
                ),
            }
        )

    if "mira sorrento" not in existing:
        rows.append(
            {
                "Name": "Mira Sorrento",
                "Owner": "SDG&E",
                "Max_Voltag": 69,
                "COUNTY": "San Diego County",
                "CITY": "San Diego",
                "Status": "Operational; supplemental reference point",
                "Source": "CPUC A.11-10-015 / OpenStreetMap location",
                "CEC_Sub_ID": "TPP_SUPPLEMENT_MIRA_SORRENTO",
                "geometry": Point(-117.20601, 32.89275),
            }
        )

    if "trout canyon" not in existing:
        rows.append(
            {
                "Name": "Trout Canyon",
                "Owner": "GridLiance West",
                "Max_Voltag": 500,
                "COUNTY": "Clark County, Nevada",
                "CITY": "Pahrump Valley",
                "Status": "Approximate reference point",
                "Source": (
                    "CAISO TPP / BLM Yellow Pine site near SR-160 and Tecopa Road"
                ),
                "CEC_Sub_ID": "TPP_APPROX_TROUT_CANYON",
                "geometry": Point(-115.77514, 36.06627),
            }
        )

    if rows:
        supplemental = gpd.GeoDataFrame(rows, geometry="geometry", crs=result.crs)
        result = gpd.GeoDataFrame(
            pd.concat([result, supplemental], ignore_index=True),
            geometry="geometry",
            crs=result.crs,
        )
    return result


def _filter_casefold(
    frame: gpd.GeoDataFrame, column: str, value: str
) -> gpd.GeoDataFrame:
    return frame[
        frame[column].fillna("").astype(str).str.strip().str.casefold()
        == value.strip().casefold()
    ]


def _resolve_with_rule(
    name: str, substations: gpd.GeoDataFrame, rule: EndpointRule
) -> tuple[Point, str]:
    selected = substations[
        substations["Name"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.casefold()
        .isin({item.casefold() for item in rule.names})
    ]
    if rule.owner:
        selected = _filter_casefold(selected, "Owner", rule.owner)
    if rule.county:
        selected = _filter_casefold(selected, "COUNTY", rule.county)
    if rule.voltage is not None:
        voltage = pd.to_numeric(selected["Max_Voltag"], errors="coerce")
        selected = selected[voltage == rule.voltage]

    if selected.empty:
        raise EndpointResolutionError(
            f"{name!r} did not match its explicit endpoint rule"
        )
    if len(selected) > 1 and not rule.combine:
        choices = selected[
            ["Name", "Owner", "Max_Voltag", "COUNTY", "CITY"]
        ].to_dict("records")
        raise EndpointResolutionError(
            f"{name!r} remains ambiguous after filtering: {choices}"
        )
    if len(selected) > 1:
        point = Point(selected.geometry.x.mean(), selected.geometry.y.mean())
        basis = " / ".join(sorted(set(selected["Name"].astype(str))))
        return point, f"{basis} complex/duplicate centroid"

    row = selected.iloc[0]
    return row.geometry, str(row["Name"])


def resolve_endpoint(
    raw_name: str, substations: gpd.GeoDataFrame
) -> tuple[Point, str]:
    """Resolve a CAISO endpoint without automatic fuzzy matching."""

    name = str(raw_name or "").strip()
    if not name:
        raise EndpointResolutionError("Blank endpoint")

    if name in ENDPOINT_RULES:
        return _resolve_with_rule(name, substations, ENDPOINT_RULES[name])

    canonical = ALIASES.get(name, name)
    selected = _filter_casefold(substations, "Name", canonical)
    if selected.empty:
        raise EndpointResolutionError(
            f"No exact or approved-alias substation match for {name!r}"
        )
    if len(selected) > 1:
        choices = selected[
            ["Name", "Owner", "Max_Voltag", "COUNTY", "CITY"]
        ].to_dict("records")
        raise EndpointResolutionError(
            f"Ambiguous endpoint {name!r}; add an explicit rule: {choices}"
        )

    row = selected.iloc[0]
    basis = str(row["Name"])
    if canonical != name:
        basis = f"{name} → {basis}"
    return row.geometry, basis


def _line_key(value: object) -> tuple[str, ...]:
    text = str(value or "").strip()
    if not text:
        return ()
    parts = re.split(r"\s*-\s*", text)
    normalized = [
        re.sub(r"[^a-z0-9]+", "", part.casefold()) for part in parts if part
    ]
    return tuple(sorted(item for item in normalized if item))


def _named_transmission_geometry(
    line_name: str, transmission: gpd.GeoDataFrame
):
    """Return an exact direction-insensitive TLine_Name match, if present."""

    key = _line_key(line_name)
    if not key or "TLine_Name" not in transmission.columns:
        return None, None
    keys = transmission["TLine_Name"].map(_line_key)
    selected = transmission[keys == key]
    if selected.empty:
        return None, None
    return unary_union(selected.geometry.values), str(
        selected["TLine_Name"].dropna().astype(str).iloc[0]
    )


def _short_segment_near_endpoint(
    transmission: gpd.GeoDataFrame,
    endpoint: Point,
    miles: float,
    owner: Optional[str] = None,
    voltage: Optional[float] = None,
):
    """Extract an approximate line-length segment near a known endpoint."""

    candidates = transmission.copy()
    if owner and "Owner" in candidates.columns:
        candidates = _filter_casefold(candidates, "Owner", owner)
    if voltage is not None and "kV" in candidates.columns:
        kv = pd.to_numeric(candidates["kV"], errors="coerce")
        candidates = candidates[kv == voltage]
    candidates = candidates[
        candidates.geometry.geom_type.isin(["LineString", "MultiLineString"])
    ]
    if candidates.empty:
        return None

    projected = candidates.to_crs("EPSG:3310")
    projected_endpoint = gpd.GeoSeries(
        [endpoint], crs="EPSG:4326"
    ).to_crs("EPSG:3310").iloc[0]
    nearest_index = projected.geometry.distance(projected_endpoint).idxmin()
    geometry = projected.loc[nearest_index].geometry
    if geometry.geom_type == "MultiLineString":
        geometry = min(
            geometry.geoms, key=lambda part: part.distance(projected_endpoint)
        )

    target_length = max(float(miles), 0.1) * 1609.344
    center = geometry.project(projected_endpoint)
    start = max(0.0, center - target_length / 2)
    end = min(geometry.length, center + target_length / 2)
    if end - start < target_length and start == 0:
        end = min(geometry.length, target_length)
    elif end - start < target_length and end == geometry.length:
        start = max(0.0, geometry.length - target_length)
    segment = substring(geometry, start, end)
    return gpd.GeoSeries([segment], crs="EPSG:3310").to_crs(
        "EPSG:4326"
    ).iloc[0]


def _clean_value(value: object):
    if pd.isna(value):
        return ""
    return value


def load_and_validate_tpp_inventory(
    manifest_path: Path | str,
    component_path: Path | str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load the official project inventory and verify component coverage.

    The manifest is the project-level source of truth. The component table may
    contain multiple rows for one project, but every official project must
    appear at least once and no unlisted project may slip into the map.
    """

    manifest = pd.read_csv(manifest_path).fillna("")
    components = pd.read_csv(component_path).fillna("")
    required_manifest = {
        "official_order",
        "project_id",
        "project_name",
        "driver",
    }
    required_components = {
        "project_name",
        "bucket",
        "endpoint_a",
        "driver",
    }
    if missing := required_manifest - set(manifest.columns):
        raise ValueError(f"TPP manifest is missing columns: {sorted(missing)}")
    if missing := required_components - set(components.columns):
        raise ValueError(f"TPP component table is missing columns: {sorted(missing)}")
    if len(manifest) != 38:
        raise ValueError(
            f"TPP manifest has {len(manifest)} projects; the approved plan has 38"
        )
    for column in ("project_id", "project_name", "official_order"):
        if manifest[column].duplicated().any():
            duplicates = manifest.loc[
                manifest[column].duplicated(keep=False), column
            ].tolist()
            raise ValueError(f"Duplicate TPP {column}: {duplicates}")
    expected_order = list(range(1, 39))
    actual_order = pd.to_numeric(
        manifest["official_order"], errors="raise"
    ).astype(int).tolist()
    if actual_order != expected_order:
        raise ValueError("TPP manifest official_order must be exactly 1 through 38")

    official_names = set(manifest["project_name"])
    component_names = set(components["project_name"])
    missing_projects = sorted(official_names - component_names)
    extra_projects = sorted(component_names - official_names)
    if missing_projects or extra_projects:
        details = []
        if missing_projects:
            details.append(f"unmapped official projects: {missing_projects}")
        if extra_projects:
            details.append(f"components absent from manifest: {extra_projects}")
        raise ValueError("TPP inventory mismatch; " + "; ".join(details))

    merged = components.merge(
        manifest[
            ["official_order", "project_id", "project_name", "driver", "status_note"]
        ],
        on="project_name",
        how="left",
        validate="many_to_one",
        suffixes=("", "_official"),
    )
    driver_mismatch = merged[
        merged["driver"].astype(str).str.casefold()
        != merged["driver_official"].astype(str).str.casefold()
    ]
    if not driver_mismatch.empty:
        raise ValueError(
            "TPP driver mismatch for: "
            + ", ".join(driver_mismatch["project_name"].unique())
        )
    merged = merged.drop(columns=["driver_official"])
    return manifest, merged


def geometry_class_for(upgrade_type: str, geometry_basis: str) -> str:
    """Return the public geometry classification used by map and legend."""

    basis = str(geometry_basis).casefold()
    if upgrade_type == "project_scope_reference":
        return "project_scope_reference"
    if upgrade_type == "new_substation":
        return "substation_new_approximate"
    if upgrade_type == "substation_upgrade":
        return "substation_existing"
    if upgrade_type == "new_line":
        return "line_new_schematic"
    if "approximate mapped line segment" in basis:
        return "line_existing_approximate"
    if "existing mapped transmission line" in basis:
        return "line_existing_mapped"
    return "line_existing_schematic"


def build_upgrades(
    csv_path: Path | str,
    substations: gpd.GeoDataFrame,
    transmission: gpd.GeoDataFrame,
    manifest_path: Path | str | None = None,
) -> gpd.GeoDataFrame:
    """Build one geometry for every row of the TPP spreadsheet."""

    if manifest_path is None:
        projects = pd.read_csv(csv_path).fillna("")
    else:
        _, projects = load_and_validate_tpp_inventory(manifest_path, csv_path)
    rows = []
    errors = []

    for source_row, project in projects.iterrows():
        bucket = str(project["bucket"]).strip().lower()
        endpoint_a = str(project.get("endpoint_a", "")).strip()
        endpoint_b = str(project.get("endpoint_b", "")).strip()
        line_name = str(project.get("line_name", "")).strip()
        geometry = None
        basis = ""
        endpoint_a_basis = ""
        endpoint_b_basis = ""

        try:
            if bucket in {"substation", "project_area"}:
                geometry, endpoint_a_basis = resolve_endpoint(
                    endpoint_a, substations
                )
                if bucket == "project_area":
                    upgrade_type = "project_scope_reference"
                    basis = (
                        "project-scope reference point at existing substation: "
                        f"{endpoint_a_basis}"
                    )
                else:
                    is_new = "new substation" in str(
                        project.get("notes", "")
                    ).casefold()
                    upgrade_type = (
                        "new_substation" if is_new else "substation_upgrade"
                    )
                    basis = (
                        f"approximate new-substation point: {endpoint_a_basis}"
                        if is_new
                        else f"existing substation point: {endpoint_a_basis}"
                    )

            elif bucket in {"new_line", "existing_line"}:
                point_a, endpoint_a_basis = resolve_endpoint(
                    endpoint_a, substations
                )
                point_b = None
                if endpoint_b:
                    point_b, endpoint_b_basis = resolve_endpoint(
                        endpoint_b, substations
                    )

                if bucket == "existing_line" and line_name:
                    geometry, matched_line = _named_transmission_geometry(
                        line_name, transmission
                    )
                    if geometry is not None:
                        basis = f"existing mapped transmission line: {matched_line}"

                if geometry is None and point_b is not None:
                    geometry = LineString(
                        [point_a.coords[0], point_b.coords[0]]
                    )
                    label = "new-line" if bucket == "new_line" else "existing-line"
                    basis = (
                        f"schematic {label} endpoint connector: "
                        f"{endpoint_a_basis} – {endpoint_b_basis}"
                    )

                if geometry is None:
                    miles = pd.to_numeric(
                        project.get("approx_miles", ""), errors="coerce"
                    )
                    if pd.isna(miles):
                        miles = 0.7
                    geometry = _short_segment_near_endpoint(
                        transmission,
                        point_a,
                        float(miles),
                        owner="SDG&E",
                        voltage=pd.to_numeric(
                            project.get("kV", ""), errors="coerce"
                        ),
                    )
                    if geometry is not None:
                        basis = (
                            "approximate mapped line segment near "
                            f"{endpoint_a_basis}"
                        )

                upgrade_type = bucket
            else:
                raise ValueError(f"Unknown bucket {bucket!r}")

            if geometry is None or geometry.is_empty:
                raise EndpointResolutionError("No geometry was produced")

            rows.append(
                {
                    "source_row": source_row + 1,
                    "official_order": _clean_value(
                        project.get("official_order", "")
                    ),
                    "project_id": _clean_value(project.get("project_id", "")),
                    "project_name": _clean_value(project["project_name"]),
                    "bucket": bucket,
                    "upgrade_type": upgrade_type,
                    "line_name": _clean_value(project.get("line_name", "")),
                    "endpoint_a": endpoint_a,
                    "endpoint_b": endpoint_b,
                    "kV": _clean_value(project.get("kV", "")),
                    "driver": _clean_value(project.get("driver", "")),
                    "approx_miles": _clean_value(
                        project.get("approx_miles", "")
                    ),
                    "notes": _clean_value(project.get("notes", "")),
                    "project_cost": _clean_value(
                        project.get("project_cost", "")
                    ),
                    "status_note": _clean_value(
                        project.get("status_note", "")
                    ),
                    "geometry_basis": basis,
                    "geometry_class": geometry_class_for(upgrade_type, basis),
                    "geometry": geometry,
                }
            )
        except Exception as exc:
            errors.append(
                f"row {source_row + 1} ({project['project_name']}): {exc}"
            )

    if errors:
        raise EndpointResolutionError(
            "TPP geometry build failed:\n  - " + "\n  - ".join(errors)
        )

    upgrades = gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:4326")
    expected_rows = len(projects)
    if len(upgrades) != expected_rows:
        raise RuntimeError(
            f"Built {len(upgrades)} of {expected_rows} TPP row geometries"
        )
    if set(upgrades["source_row"]) != set(range(1, expected_rows + 1)):
        raise RuntimeError("TPP source-row validation failed")
    return upgrades
