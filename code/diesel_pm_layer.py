"""CalEnviroScreen 5.0 diesel particulate matter map layers.

This module intentionally uses the final July 2026 CalEnviroScreen 5.0
release, not the earlier draft.  The raw indicator is an emissions estimate
from on-road and non-road sources within and near populated blocks; it is not
an ambient diesel-PM concentration measurement.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional, Union

import folium
import geopandas as gpd
import pandas as pd
from branca.colormap import linear

from map_design import DIESEL_PM_SCALE


CES_VERSION = "CalEnviroScreen 5.0 (final)"
CES_RELEASE_DATE = "2026-07-01"
CES_DATASET_PAGE = "https://lab.data.ca.gov/dataset/calenviroscreen-5-0"
CES_SHAPEFILE_URL = (
    "https://data.ca.gov/dataset/72b28c84-ceac-4886-9f71-d422470d2223/"
    "resource/e3d16016-1828-424f-85a6-f7731033d338/download/"
    "calenviroscreen50results_f_070126.shp.zip"
)
CES_DATA_DICTIONARY_URL = (
    "https://data.ca.gov/dataset/72b28c84-ceac-4886-9f71-d422470d2223/"
    "resource/31ddb21a-44bb-4cb0-81d8-6e2f80ee359d/download/"
    "final-calenviroscreen-5.0-data-dictionary.pdf"
)
CES_TECHNICAL_REPORT_URL = (
    "https://oehha.ca.gov/sites/default/files/media/2026-06/"
    "calenviroscreen50reportf2026.pdf"
)
CES_FEATURE_SERVICE = (
    "https://services1.arcgis.com/PCHfdHz4GlDNAhBb/arcgis/rest/services/"
    "calenviroscreen50results_F_070126_gdb/FeatureServer/0"
)

MODULE_DIR = Path(__file__).resolve().parent
DEFAULT_ARCHIVE = (
    MODULE_DIR
    / "data"
    / "calenviroscreen"
    / "calenviroscreen50results_f_070126.shp.zip"
)
ARCHIVE_MEMBER = (
    "calenviroscreen50results_F_070126.shp/CES5_final_shapefile.shp"
)

EXPECTED_TRACTS = 9_106
EXPECTED_DIESEL_MISSING = 9
MISSING_SENTINEL = -999
TOP_QUINTILE_THRESHOLD = 80.0

NORMALIZED_COLUMNS = [
    "tract_geoid",
    "county",
    "approximate_location",
    "population_2024",
    "diesel_pm_tons_per_year",
    "diesel_pm_percentile",
    "diesel_pm_top_quintile",
    "diesel_pm_status",
    "geometry",
]


def _find_column(frame: gpd.GeoDataFrame, *candidates: str) -> str:
    """Return the first source column present, allowing SHP and API schemas."""
    casefolded = {str(column).casefold(): str(column) for column in frame.columns}
    for candidate in candidates:
        if candidate in frame.columns:
            return candidate
        match = casefolded.get(candidate.casefold())
        if match is not None:
            return match
    raise KeyError(
        f"None of {candidates!r} found in CalEnviroScreen fields: "
        f"{list(frame.columns)!r}"
    )


def _tract_geoids(values: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(values, errors="raise")
    if numeric.isna().any():
        raise ValueError("CalEnviroScreen contains a missing census tract ID")
    if not (numeric % 1 == 0).all():
        raise ValueError("CalEnviroScreen contains a non-integer census tract ID")
    return numeric.astype("int64").astype(str).str.zfill(11)


def validate_diesel_pm_data(
    tracts: gpd.GeoDataFrame,
    *,
    strict_release: bool = True,
) -> Dict[str, Union[int, float, str]]:
    """Validate normalized data and return a compact quality-control summary."""
    missing_columns = set(NORMALIZED_COLUMNS) - set(tracts.columns)
    if missing_columns:
        raise ValueError(f"Missing normalized fields: {sorted(missing_columns)}")
    if tracts.crs is None:
        raise ValueError("CalEnviroScreen geometry has no coordinate reference system")
    if tracts["tract_geoid"].duplicated().any():
        raise ValueError("CalEnviroScreen contains duplicate census tract IDs")
    if tracts.geometry.isna().any() or tracts.geometry.is_empty.any():
        raise ValueError("CalEnviroScreen contains missing or empty geometry")
    if not tracts.geometry.is_valid.all():
        raise ValueError("CalEnviroScreen contains invalid tract geometry")

    raw = tracts["diesel_pm_tons_per_year"]
    percentile = tracts["diesel_pm_percentile"]
    if not raw.dropna().between(0, float("inf"), inclusive="both").all():
        raise ValueError("Non-missing diesel-PM emissions must be nonnegative")
    if not percentile.dropna().between(0, 100, inclusive="both").all():
        raise ValueError("Non-missing diesel-PM percentiles must be within 0-100")
    if not raw.isna().equals(percentile.isna()):
        raise ValueError("Raw and percentile diesel-PM missing-value masks differ")

    summary: Dict[str, Union[int, float, str]] = {
        "release": CES_VERSION,
        "row_count": int(len(tracts)),
        "unique_tracts": int(tracts["tract_geoid"].nunique()),
        "missing_raw": int(raw.isna().sum()),
        "missing_percentile": int(percentile.isna().sum()),
        "top_quintile_tracts": int(
            tracts["diesel_pm_top_quintile"].fillna(False).sum()
        ),
        "minimum_percentile": float(percentile.min()),
        "maximum_percentile": float(percentile.max()),
        "invalid_geometries": int((~tracts.geometry.is_valid).sum()),
    }
    if strict_release:
        if len(tracts) != EXPECTED_TRACTS:
            raise ValueError(
                f"Expected {EXPECTED_TRACTS:,} final CES 5.0 tracts; "
                f"found {len(tracts):,}"
            )
        if raw.isna().sum() != EXPECTED_DIESEL_MISSING:
            raise ValueError(
                f"Expected {EXPECTED_DIESEL_MISSING} missing diesel-PM values; "
                f"found {raw.isna().sum()}"
            )
    return summary


def load_diesel_pm_data(
    archive_path: Union[str, Path] = DEFAULT_ARCHIVE,
    *,
    target_crs: Optional[Union[str, int]] = "EPSG:4326",
    strict_release: bool = True,
) -> gpd.GeoDataFrame:
    """Load the final CES 5.0 archive into a publication-ready tract schema.

    The source shapefile stores missing numeric values as ``-999``.  They are
    converted to proper nulls before the top-quintile flag is calculated.
    Source metadata and a validation summary are retained in ``GeoDataFrame.attrs``.
    """
    archive = Path(archive_path)
    if not archive.exists():
        raise FileNotFoundError(
            f"CalEnviroScreen archive not found at {archive}. "
            f"Download the final release from {CES_SHAPEFILE_URL}"
        )

    source = gpd.read_file(f"zip://{archive}!{ARCHIVE_MEMBER}")
    tract_col = _find_column(source, "tract")
    county_col = _find_column(source, "county")
    location_col = _find_column(source, "approx_loc", "ApproxLoc")
    population_col = _find_column(source, "ACS2024Pop", "Population")
    raw_col = _find_column(source, "diesel", "Diesel_PM")
    percentile_col = _find_column(source, "dieselP", "Diesel_PM_Pctl")

    raw = pd.to_numeric(source[raw_col], errors="coerce").replace(
        MISSING_SENTINEL, pd.NA
    )
    percentile = pd.to_numeric(source[percentile_col], errors="coerce").replace(
        MISSING_SENTINEL, pd.NA
    )
    top_quintile = percentile.ge(TOP_QUINTILE_THRESHOLD).astype("boolean")
    top_quintile.loc[percentile.isna()] = pd.NA

    normalized = gpd.GeoDataFrame(
        {
            "tract_geoid": _tract_geoids(source[tract_col]),
            "county": source[county_col].astype("string"),
            "approximate_location": source[location_col].astype("string"),
            "population_2024": pd.to_numeric(
                source[population_col], errors="coerce"
            ).astype("Int64"),
            "diesel_pm_tons_per_year": raw.astype("Float64"),
            "diesel_pm_percentile": percentile.astype("Float64"),
            "diesel_pm_top_quintile": top_quintile,
            "diesel_pm_status": pd.Series(
                ["missing" if pd.isna(value) else "reported" for value in raw],
                dtype="string",
            ),
        },
        geometry=source.geometry,
        crs=source.crs,
    )
    if target_crs is not None:
        normalized = normalized.to_crs(target_crs)

    validation = validate_diesel_pm_data(
        normalized, strict_release=strict_release
    )
    normalized.attrs.update(
        {
            "source": "California OEHHA",
            "dataset": CES_VERSION,
            "release_date": CES_RELEASE_DATE,
            "dataset_page": CES_DATASET_PAGE,
            "shapefile_url": CES_SHAPEFILE_URL,
            "data_dictionary_url": CES_DATA_DICTIONARY_URL,
            "technical_report_url": CES_TECHNICAL_REPORT_URL,
            "feature_service": CES_FEATURE_SERVICE,
            "raw_source_field": raw_col,
            "percentile_source_field": percentile_col,
            "missing_value_note": (
                "The source shapefile encodes NA as -999; normalized values are null."
            ),
            "interpretation_note": (
                "The indicator estimates diesel PM emissions from on-road and "
                "non-road sources within and near populated blocks. It is not an "
                "ambient concentration measurement and does not include a proposed "
                "data center's future backup-generator emissions."
            ),
            "validation": validation,
        }
    )
    return normalized


def make_diesel_pm_layer(
    tracts: Optional[gpd.GeoDataFrame] = None,
    *,
    mode: str = "percentile",
    name: Optional[str] = None,
    show: bool = False,
    top_quintile_threshold: float = TOP_QUINTILE_THRESHOLD,
    simplify_tolerance: Optional[float] = 0.0005,
    pane: Optional[str] = None,
) -> folium.FeatureGroup:
    """Build a Folium overlay for statewide percentile or top-quintile tracts.

    ``mode="percentile"`` retains all tracts and draws missing values in gray.
    ``mode="top_quintile"`` shows only tracts at or above the threshold.
    Simplification occurs only on a copy used for web display.
    """
    if mode not in {"percentile", "top_quintile"}:
        raise ValueError("mode must be 'percentile' or 'top_quintile'")
    if not 0 <= top_quintile_threshold <= 100:
        raise ValueError("top_quintile_threshold must be between 0 and 100")

    data = load_diesel_pm_data() if tracts is None else tracts.copy()
    validate_diesel_pm_data(data, strict_release=False)
    if data.crs is None or data.crs.to_epsg() != 4326:
        data = data.to_crs("EPSG:4326")

    if mode == "top_quintile":
        data = data.loc[
            data["diesel_pm_percentile"].ge(top_quintile_threshold)
        ].copy()
    if simplify_tolerance:
        data.geometry = data.geometry.simplify(
            simplify_tolerance, preserve_topology=True
        )

    layer_name = name or (
        "CES 5.0 diesel PM percentile"
        if mode == "percentile"
        else f"CES 5.0 diesel PM top quintile (≥{top_quintile_threshold:g})"
    )
    layer = folium.FeatureGroup(
        name=layer_name,
        overlay=True,
        control=True,
        show=show,
    )
    colormap = linear.Purples_09.scale(0, 100)
    colormap.caption = "CalEnviroScreen 5.0 diesel PM percentile"

    def percentile_color(value: float) -> str:
        classes = DIESEL_PM_SCALE["classes"]
        for index, item in enumerate(classes):
            is_last = index == len(classes) - 1
            if value >= item["minimum"] and (
                value < item["maximum"]
                or is_last and value <= item["maximum"]
            ):
                return item["color"]
        return classes[-1]["color"]

    def style_function(feature: dict) -> dict:
        value = feature["properties"].get("diesel_pm_percentile")
        if value is None:
            return {
                "fillColor": "#bdbdbd",
                "color": "#8c8c8c",
                "weight": 0.25,
                "fillOpacity": 0.25,
            }
        return {
            "fillColor": (
                "#54278F"
                if mode == "top_quintile"
                else percentile_color(float(value))
            ),
            "color": "#3F2B68" if mode == "top_quintile" else "#6F6585",
            "weight": 0.7 if mode == "top_quintile" else 0.3,
            "fillOpacity": 0.72 if mode == "top_quintile" else 0.64,
        }

    folium.GeoJson(
        data=data.to_json(drop_id=True),
        name=layer_name,
        style_function=style_function,
        highlight_function=lambda _feature: {
            "weight": 1.5,
            "color": "#222222",
            "fillOpacity": 0.82,
        },
        tooltip=folium.GeoJsonTooltip(
            fields=[
                "tract_geoid",
                "county",
                "approximate_location",
                "diesel_pm_tons_per_year",
                "diesel_pm_percentile",
                "diesel_pm_status",
            ],
            aliases=[
                "Census tract:",
                "County:",
                "Approximate location:",
                "Diesel PM emissions (tons/year):",
                "Diesel PM percentile:",
                "Data status:",
            ],
            localize=True,
            sticky=False,
        ),
        smooth_factor=0.5,
        zoom_on_click=False,
        pane=pane,
    ).add_to(layer)
    return layer


def add_diesel_pm_layers(
    map_object: folium.Map,
    tracts: Optional[gpd.GeoDataFrame] = None,
    *,
    show_percentile: bool = False,
    show_top_quintile: bool = False,
) -> folium.Map:
    """Add both mutually useful CES diesel-PM overlays to a Folium map."""
    data = load_diesel_pm_data() if tracts is None else tracts
    make_diesel_pm_layer(
        data, mode="percentile", show=show_percentile
    ).add_to(map_object)
    make_diesel_pm_layer(
        data, mode="top_quintile", show=show_top_quintile
    ).add_to(map_object)
    return map_object
