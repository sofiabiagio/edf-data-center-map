"""Official California reliability-area and electric-territory layers.

The loaders cache normalized WGS84 polygons in ``code/data/lra_utility``.
They intentionally preserve overlapping service areas.  In particular,
Community Choice Aggregators (CCAs) overlap the distribution utilities whose
wires serve the same customers.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, Optional, Tuple

import folium
import geopandas as gpd
import pandas as pd
import requests
from shapely import make_valid
from shapely.geometry import GeometryCollection, MultiPolygon, Polygon
from shapely.ops import unary_union


DATA_DIR = Path(__file__).resolve().parent / "data" / "lra_utility"
CACHE_PATH = DATA_DIR / "lra_utility_layers.gpkg"
MANIFEST_PATH = DATA_DIR / "source_manifest.json"
VALIDATION_PATH = DATA_DIR / "validation_report.json"

LRA_SERVICE = (
    "https://gis.cpuc.ca.gov/server/rest/services/Hosted/"
    "LocalReliabilityAreas/FeatureServer/0"
)
UTILITY_IOU_POU_SERVICE = (
    "https://services3.arcgis.com/bWPjFyq029ChCGur/arcgis/rest/services/"
    "ElectricLoadServingEntities_IOU_POU/FeatureServer/0"
)
UTILITY_OTHER_SERVICE = (
    "https://services3.arcgis.com/bWPjFyq029ChCGur/arcgis/rest/services/"
    "ElectricLoadServingEntities_Other/FeatureServer/0"
)

LRA_ITEM_ID = "04e24bc16e2d4ebaa53e10259b7242c1"
UTILITY_IOU_POU_ITEM_ID = "30410214d637434ba1003cbdcc32cf55"
UTILITY_OTHER_ITEM_ID = "07224640a2fe42f89399be796e7b8810"

LRA_SOURCE_UPDATED_UTC = "2023-01-26T19:24:02Z"
UTILITY_IOU_POU_UPDATED_UTC = "2025-08-28T16:01:56Z"
UTILITY_OTHER_UPDATED_UTC = "2025-08-28T16:04:24Z"

UTILITY_BOUNDARY_CAVEAT = (
    "CEC states that these boundaries are approximate; contact the relevant "
    "load-serving entity for authoritative territory information."
)
OTHER_UTILITY_CAVEAT = (
    "CEC states that not all load-serving entities are represented. CCA "
    "polygons overlap the distribution utility that owns the local wires."
)

MAJOR_IOU_ACRONYMS = {"PG&E", "SCE", "SDG&E"}
SOURCE_FIELDS = [
    "OBJECTID",
    "Acronym",
    "Utility",
    "AgencyNum",
    "Type",
    "URL",
    "Phone",
    "Address",
    "HIFLD_ID",
]


def _request_json(url: str, params: Dict[str, object]) -> dict:
    response = requests.get(url, params=params, timeout=180)
    response.raise_for_status()
    payload = response.json()
    if "error" in payload:
        raise RuntimeError(f"ArcGIS request failed: {payload['error']}")
    return payload


def _download_arcgis_geojson(
    service_url: str,
    *,
    out_fields: Iterable[str],
) -> Tuple[gpd.GeoDataFrame, int]:
    """Download every feature, using count-first deterministic pagination."""
    expected = int(
        _request_json(
            f"{service_url}/query",
            {"where": "1=1", "returnCountOnly": "true", "f": "json"},
        )["count"]
    )
    metadata = _request_json(service_url, {"f": "json"})
    page_size = min(int(metadata.get("maxRecordCount", 2000)), 2000)
    oid_field = metadata.get("objectIdField") or metadata.get(
        "objectIdFieldName"
    )
    if not oid_field:
        oid_candidates = [
            field["name"]
            for field in metadata.get("fields", [])
            if field.get("type") == "esriFieldTypeOID"
        ]
        if not oid_candidates:
            raise RuntimeError(f"No object ID field advertised by {service_url}")
        oid_field = oid_candidates[0]

    features = []
    for offset in range(0, expected, page_size):
        payload = _request_json(
            f"{service_url}/query",
            {
                "where": "1=1",
                "outFields": ",".join(out_fields),
                "returnGeometry": "true",
                "outSR": 4326,
                "orderByFields": oid_field,
                "resultOffset": offset,
                "resultRecordCount": page_size,
                "f": "geojson",
            },
        )
        page = payload.get("features", [])
        if not page:
            raise RuntimeError(
                f"Pagination stopped at {offset:,} of {expected:,} features"
            )
        features.extend(page)

    if len(features) != expected:
        raise RuntimeError(
            f"Downloaded {len(features):,}; service count is {expected:,}"
        )
    frame = gpd.GeoDataFrame.from_features(features, crs="EPSG:4326")
    return frame, expected


def _polygonal_only(geometry):
    """Repair geometry and discard only non-polygon fragments."""
    if geometry is None or geometry.is_empty:
        return geometry
    repaired = geometry if geometry.is_valid else make_valid(geometry)
    if isinstance(repaired, (Polygon, MultiPolygon)):
        return repaired
    if isinstance(repaired, GeometryCollection):
        polygons = [
            part
            for part in repaired.geoms
            if isinstance(part, (Polygon, MultiPolygon)) and not part.is_empty
        ]
        return unary_union(polygons) if polygons else None
    return None


def _repair_polygons(frame: gpd.GeoDataFrame) -> Tuple[gpd.GeoDataFrame, int]:
    result = frame.copy()
    invalid_before = int((~result.geometry.is_valid).sum())
    result.geometry = result.geometry.map(_polygonal_only)
    result = result[
        result.geometry.notna() & ~result.geometry.is_empty
    ].copy()
    if not result.geometry.is_valid.all():
        raise ValueError("Polygon repair left invalid geometries")
    if not result.geom_type.isin(["Polygon", "MultiPolygon"]).all():
        raise ValueError("Non-polygon geometry remains after normalization")
    return result, invalid_before


def _clean_text(series: pd.Series) -> pd.Series:
    return series.astype("string").str.strip().replace({"": pd.NA})


def _normalize_lra(raw: gpd.GeoDataFrame) -> Tuple[gpd.GeoDataFrame, int]:
    frame = raw.rename(
        columns={
            "fid": "source_object_id",
            "name": "lra_name",
            "type": "lra_type",
            "current_": "current_flag",
        }
    )
    frame["lra_name"] = _clean_text(frame["lra_name"])
    frame["lra_type"] = _clean_text(frame["lra_type"])
    frame["is_current"] = (
        _clean_text(frame["current_flag"]).str.upper().eq("Y")
    )
    frame["source_agency"] = "California Public Utilities Commission"
    frame["source_item_id"] = LRA_ITEM_ID
    frame["source_url"] = LRA_SERVICE
    frame["source_updated_utc"] = LRA_SOURCE_UPDATED_UTC
    keep = [
        "source_object_id",
        "lra_name",
        "lra_type",
        "is_current",
        "source_agency",
        "source_item_id",
        "source_url",
        "source_updated_utc",
        "geometry",
    ]
    return _repair_polygons(frame[keep].to_crs(4326))


def _ownership_class(service_type: str) -> str:
    return {
        "IOU": "investor_owned",
        "POU": "publicly_owned",
        "CO-OP": "cooperative",
        "TRIBAL": "tribal",
        "CCA": "community_choice_aggregator",
        "ADMIN": "federal_administration",
    }.get(service_type, "other")


def _territory_role(service_type: str) -> str:
    if service_type in {"IOU", "POU", "CO-OP", "TRIBAL"}:
        return "distribution_utility"
    if service_type == "CCA":
        return "overlapping_load_supplier"
    if service_type == "ADMIN":
        return "power_administration"
    return "other"


def _normalize_utilities(
    raw: gpd.GeoDataFrame,
    *,
    source_group: str,
    source_item_id: str,
    source_url: str,
    source_updated_utc: str,
) -> Tuple[gpd.GeoDataFrame, int]:
    frame = raw.rename(
        columns={
            "OBJECTID": "source_object_id",
            "Acronym": "utility_acronym",
            "Utility": "utility_name",
            "AgencyNum": "agency_number",
            "Type": "service_type",
            "URL": "utility_url",
            "Phone": "utility_phone",
            "Address": "utility_address",
            "HIFLD_ID": "hifld_id",
        }
    )
    for field in [
        "utility_acronym",
        "utility_name",
        "service_type",
        "utility_url",
        "utility_phone",
        "utility_address",
        "hifld_id",
    ]:
        frame[field] = _clean_text(frame[field])
    frame["service_type"] = frame["service_type"].str.upper()
    frame["is_iou"] = frame["service_type"].eq("IOU")
    frame["iou_tier"] = "not_iou"
    frame.loc[frame["is_iou"], "iou_tier"] = "small_iou"
    frame.loc[
        frame["utility_acronym"].isin(MAJOR_IOU_ACRONYMS), "iou_tier"
    ] = "major_iou"
    frame["ownership_class"] = frame["service_type"].map(_ownership_class)
    frame["territory_role"] = frame["service_type"].map(_territory_role)
    frame["source_group"] = source_group
    frame["source_agency"] = "California Energy Commission"
    frame["source_item_id"] = source_item_id
    frame["source_url"] = source_url
    frame["source_updated_utc"] = source_updated_utc
    frame["boundary_caveat"] = UTILITY_BOUNDARY_CAVEAT
    frame.loc[
        frame["source_group"].eq("other_lse"), "boundary_caveat"
    ] += " " + OTHER_UTILITY_CAVEAT
    keep = [
        "source_object_id",
        "utility_acronym",
        "utility_name",
        "agency_number",
        "service_type",
        "is_iou",
        "iou_tier",
        "ownership_class",
        "territory_role",
        "utility_url",
        "utility_phone",
        "utility_address",
        "hifld_id",
        "source_group",
        "source_agency",
        "source_item_id",
        "source_url",
        "source_updated_utc",
        "boundary_caveat",
        "geometry",
    ]
    return _repair_polygons(frame[keep].to_crs(4326))


def refresh_layers() -> Tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    """Download, normalize, validate, and atomically replace the cache."""
    lra_raw, lra_expected = _download_arcgis_geojson(
        LRA_SERVICE,
        out_fields=["fid", "objectid", "name", "type", "current_"],
    )
    iou_pou_raw, iou_pou_expected = _download_arcgis_geojson(
        UTILITY_IOU_POU_SERVICE,
        out_fields=SOURCE_FIELDS,
    )
    other_raw, other_expected = _download_arcgis_geojson(
        UTILITY_OTHER_SERVICE,
        out_fields=SOURCE_FIELDS,
    )

    lra, lra_invalid = _normalize_lra(lra_raw)
    iou_pou, iou_pou_invalid = _normalize_utilities(
        iou_pou_raw,
        source_group="iou_pou",
        source_item_id=UTILITY_IOU_POU_ITEM_ID,
        source_url=UTILITY_IOU_POU_SERVICE,
        source_updated_utc=UTILITY_IOU_POU_UPDATED_UTC,
    )
    other, other_invalid = _normalize_utilities(
        other_raw,
        source_group="other_lse",
        source_item_id=UTILITY_OTHER_ITEM_ID,
        source_url=UTILITY_OTHER_SERVICE,
        source_updated_utc=UTILITY_OTHER_UPDATED_UTC,
    )
    utilities = gpd.GeoDataFrame(
        pd.concat([iou_pou, other], ignore_index=True),
        geometry="geometry",
        crs="EPSG:4326",
    )

    report = validate_layers(lra, utilities)
    if lra_expected != len(lra):
        raise ValueError("LRA normalization unexpectedly removed a feature")
    if iou_pou_expected + other_expected != len(utilities):
        raise ValueError("Utility normalization unexpectedly removed a feature")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    temporary = CACHE_PATH.with_name(f"{CACHE_PATH.stem}.tmp.gpkg")
    if temporary.exists():
        temporary.unlink()
    lra.to_file(temporary, layer="local_reliability_areas", driver="GPKG")
    utilities.to_file(
        temporary, layer="electric_service_areas", driver="GPKG", mode="a"
    )
    temporary.replace(CACHE_PATH)

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    manifest = {
        "cache_created_utc": now,
        "crs": "EPSG:4326",
        "sources": {
            "local_reliability_areas": {
                "agency": "California Public Utilities Commission",
                "item_id": LRA_ITEM_ID,
                "feature_service": LRA_SERVICE,
                "source_last_edit_utc": LRA_SOURCE_UPDATED_UTC,
                "features": lra_expected,
                "invalid_source_geometries_repaired": lra_invalid,
            },
            "electric_service_areas_iou_pou": {
                "agency": "California Energy Commission",
                "item_id": UTILITY_IOU_POU_ITEM_ID,
                "feature_service": UTILITY_IOU_POU_SERVICE,
                "source_last_edit_utc": UTILITY_IOU_POU_UPDATED_UTC,
                "features": iou_pou_expected,
                "invalid_source_geometries_repaired": iou_pou_invalid,
                "caveat": UTILITY_BOUNDARY_CAVEAT,
            },
            "electric_service_areas_other": {
                "agency": "California Energy Commission",
                "item_id": UTILITY_OTHER_ITEM_ID,
                "feature_service": UTILITY_OTHER_SERVICE,
                "source_last_edit_utc": UTILITY_OTHER_UPDATED_UTC,
                "features": other_expected,
                "invalid_source_geometries_repaired": other_invalid,
                "caveat": OTHER_UTILITY_CAVEAT,
            },
        },
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n")
    VALIDATION_PATH.write_text(json.dumps(report, indent=2) + "\n")
    return lra, utilities


def _load_cached_layer(layer: str) -> gpd.GeoDataFrame:
    if not CACHE_PATH.exists():
        refresh_layers()
    return gpd.read_file(CACHE_PATH, layer=layer).to_crs(4326)


def load_lra(*, current_only: bool = True) -> gpd.GeoDataFrame:
    """Load official CPUC/CEC LRA polygons (not a georeferenced image)."""
    frame = _load_cached_layer("local_reliability_areas")
    return frame[frame["is_current"]].copy() if current_only else frame


def load_utility_territories(
    *,
    distribution_only: bool = True,
    iou_only: bool = False,
) -> gpd.GeoDataFrame:
    """Load CEC service areas.

    ``distribution_only`` excludes overlapping CCAs and WAPA.  This is the
    correct default for assigning the utility whose wires serve a data center.
    Set it to false to inspect every published CEC load-serving-entity polygon.
    """
    frame = _load_cached_layer("electric_service_areas")
    if distribution_only:
        frame = frame[frame["territory_role"] == "distribution_utility"]
    if iou_only:
        frame = frame[frame["is_iou"]]
    return frame.copy()


def validate_layers(
    lra: Optional[gpd.GeoDataFrame] = None,
    utilities: Optional[gpd.GeoDataFrame] = None,
) -> dict:
    """Return publication-oriented structural validation results."""
    if lra is None:
        lra = load_lra(current_only=False)
    if utilities is None:
        utilities = load_utility_territories(distribution_only=False)
    distribution = utilities[
        utilities["territory_role"] == "distribution_utility"
    ]
    bounds = {
        "lra": [round(float(value), 6) for value in lra.total_bounds],
        "utilities": [
            round(float(value), 6) for value in utilities.total_bounds
        ],
    }
    return {
        "lra_features": int(len(lra)),
        "current_lra_features": int(lra["is_current"].sum()),
        "lra_names": sorted(lra["lra_name"].dropna().tolist()),
        "utility_features_all_published_lse": int(len(utilities)),
        "utility_features_distribution": int(len(distribution)),
        "utility_features_iou": int(utilities["is_iou"].sum()),
        "utility_type_counts": {
            str(key): int(value)
            for key, value in utilities["service_type"]
            .value_counts(dropna=False)
            .items()
        },
        "crs_is_wgs84": bool(lra.crs == "EPSG:4326")
        and bool(utilities.crs == "EPSG:4326"),
        "all_geometries_nonempty": bool(
            lra.geometry.notna().all()
            and (~lra.geometry.is_empty).all()
            and utilities.geometry.notna().all()
            and (~utilities.geometry.is_empty).all()
        ),
        "all_geometries_valid": bool(
            lra.geometry.is_valid.all() and utilities.geometry.is_valid.all()
        ),
        "all_geometries_polygonal": bool(
            lra.geom_type.isin(["Polygon", "MultiPolygon"]).all()
            and utilities.geom_type.isin(["Polygon", "MultiPolygon"]).all()
        ),
        "bounds_lon_lat": bounds,
        "notes": [
            "LRAs cover constrained local areas, not the entire state.",
            "CEC service boundaries are approximate, not legal boundaries.",
            "CCA areas overlap distribution utilities and are excluded by the "
            "default utility loader.",
        ],
    }


def match_points_to_lra(points: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Return a left, one-to-many point/LRA spatial match."""
    return _match_points(
        points,
        load_lra(),
        [
            "lra_name",
            "lra_type",
            "is_current",
            "source_updated_utc",
        ],
    )


def match_points_to_utilities(
    points: gpd.GeoDataFrame,
    *,
    distribution_only: bool = True,
    iou_only: bool = False,
) -> gpd.GeoDataFrame:
    """Return a left, one-to-many point/utility spatial match."""
    territories = load_utility_territories(
        distribution_only=distribution_only, iou_only=iou_only
    )
    return _match_points(
        points,
        territories,
        [
            "utility_name",
            "utility_acronym",
            "service_type",
            "is_iou",
            "iou_tier",
            "ownership_class",
            "territory_role",
            "source_updated_utc",
            "boundary_caveat",
        ],
    )


def _match_points(
    points: gpd.GeoDataFrame,
    regions: gpd.GeoDataFrame,
    region_fields: Iterable[str],
) -> gpd.GeoDataFrame:
    if points.crs is None:
        raise ValueError("Point GeoDataFrame must have a CRS")
    if not points.geom_type.eq("Point").all():
        raise ValueError("Spatial assignment accepts Point geometries only")
    prepared = points.to_crs(4326).copy()
    index_label = prepared.index.name or "point_index"
    while index_label in prepared.columns:
        index_label = f"source_{index_label}"
    prepared[index_label] = prepared.index
    row_id = "_point_row_id"
    while row_id in prepared.columns:
        row_id = f"source_{row_id}"
    prepared[row_id] = range(len(prepared))
    keep = [field for field in region_fields if field in regions.columns]
    joined = gpd.sjoin(
        prepared,
        regions[keep + ["geometry"]],
        how="left",
        predicate="intersects",
    )
    joined = joined.drop(columns=["index_right"])
    joined["region_match_count"] = joined.groupby(row_id)[row_id].transform(
        "size"
    )
    unmatched = joined[keep].isna().all(axis=1)
    joined.loc[unmatched, "region_match_count"] = 0
    return joined.drop(columns=[row_id])


def simplify_for_web(
    frame: gpd.GeoDataFrame,
    *,
    tolerance_m: float = 100.0,
    max_total_area_change: float = 0.005,
) -> gpd.GeoDataFrame:
    """Create a topology-preserving display copy with an area-drift guard."""
    if tolerance_m <= 0:
        return frame.copy()
    projected = frame.to_crs(3310)
    before = float(projected.geometry.area.sum())
    simplified = projected.copy()
    simplified.geometry = projected.geometry.simplify(
        tolerance_m, preserve_topology=True
    )
    simplified, _ = _repair_polygons(simplified)
    after = float(simplified.geometry.area.sum())
    drift = abs(after - before) / before if before else 0.0
    if drift > max_total_area_change:
        raise ValueError(
            f"Simplification area drift {drift:.3%} exceeds "
            f"{max_total_area_change:.3%}"
        )
    result = simplified.to_crs(frame.crs)
    result, _ = _repair_polygons(result)
    return result


def add_lra_layer(
    map_object: folium.Map,
    *,
    frame: Optional[gpd.GeoDataFrame] = None,
    show: bool = False,
    pane: Optional[str] = None,
) -> folium.FeatureGroup:
    frame = load_lra() if frame is None else frame
    group = folium.FeatureGroup(
        name="Local Reliability Areas", show=show, overlay=True
    )
    folium.GeoJson(
        frame,
        style_function=lambda _: {
            "color": "#0033CC",
            "weight": 2,
            "dashArray": "7 5",
            "fillColor": "#33CCFF",
            "fillOpacity": 0.05,
        },
        highlight_function=lambda _: {"weight": 3.5, "fillOpacity": 0.08},
        tooltip=folium.GeoJsonTooltip(
            fields=["lra_name", "is_current", "source_updated_utc"],
            aliases=[
                "Local reliability area",
                "Current in published source",
                "Source last edited (UTC)",
            ],
            sticky=False,
        ),
        name="Local Reliability Areas",
        pane=pane,
    ).add_to(group)
    group.add_to(map_object)
    return group


def add_utility_layer(
    map_object: folium.Map,
    *,
    frame: Optional[gpd.GeoDataFrame] = None,
    distribution_only: bool = True,
    iou_only: bool = False,
    show: bool = False,
    pane: Optional[str] = None,
) -> folium.FeatureGroup:
    if frame is None:
        frame = load_utility_territories(
            distribution_only=distribution_only, iou_only=iou_only
        )
    colors = {
        "investor_owned": "#376F83",
        "publicly_owned": "#5e3c99",
        "cooperative": "#1b9e77",
        "tribal": "#7570b3",
        "community_choice_aggregator": "#d95f02",
        "federal_administration": "#666666",
        "other": "#999999",
    }
    iou_colors = {
        "Pacific Gas & Electric Company": "#007C78",
        "Southern California Edison": "#B7791F",
        "San Diego Gas & Electric": "#2B6CB0",
        "PacifiCorp": "#6B46C1",
        "Liberty Utilities": "#A61B5B",
        "Bear Valley Electric Service": "#4A5568",
    }

    def style(feature):
        ownership = feature["properties"].get("ownership_class", "other")
        utility_name = feature["properties"].get("utility_name")
        color = iou_colors.get(
            utility_name,
            colors.get(ownership, colors["other"]),
        )
        return {
            "color": color,
            "weight": 1.25,
            "fillColor": color,
            "fillOpacity": 0.045,
        }

    label = "IOU Service Territories" if iou_only else "Electric Utility Areas"
    group = folium.FeatureGroup(name=label, show=show, overlay=True)
    folium.GeoJson(
        frame,
        style_function=style,
        highlight_function=lambda _: {"weight": 2.5, "fillOpacity": 0.11},
        tooltip=folium.GeoJsonTooltip(
            fields=[
                "utility_name",
                "utility_acronym",
                "service_type",
                "ownership_class",
                "source_updated_utc",
                "boundary_caveat",
            ],
            aliases=[
                "Utility",
                "Acronym",
                "Type",
                "Ownership",
                "Source last edited (UTC)",
                "Boundary note",
            ],
            sticky=False,
        ),
        name=label,
        pane=pane,
    ).add_to(group)
    group.add_to(map_object)
    return group


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Download authoritative services and replace the local cache.",
    )
    args = parser.parse_args()
    if args.refresh or not CACHE_PATH.exists():
        lra, utilities = refresh_layers()
    else:
        lra = load_lra(current_only=False)
        utilities = load_utility_territories(distribution_only=False)
    print(json.dumps(validate_layers(lra, utilities), indent=2))


if __name__ == "__main__":
    main()
