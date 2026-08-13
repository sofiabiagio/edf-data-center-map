"""Build a defensible tract-level PSPS frequency layer from CPUC POSTSR2A data.

The source metric ``MaxEvents`` is defined by the CPUC template as the maximum
number of de-energization events impacting any customer account in a census
tract in each month. This module sums those *monthly maxima* across the selected
years. The result is a frequency proxy; it is not a count of distinct outages
in a tract and not the history of one identified customer.

Only positive-impact tract records are present in the geodatabases. Therefore,
the metric layer contains only reported-impact polygons. The optional map
context draws other 2010 Census tracts in gray, without assigning them zero,
because POSTSR2A alone does not distinguish a covered zero-impact tract from an
area outside the submitting utilities' service territories.

The utility filings use mostly 2010 census geography, with a small number of
2025 SDG&E records using 2020 tract identifiers. All records are normalized to
2010-equivalent tracts for a non-overlapping two-year choropleth. Exact 2010
GEOIDs are preserved; newer or local identifiers are assigned by the submitted
polygon's representative point.
"""

from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path
from typing import Iterable, Optional, Sequence

import folium
import geopandas as gpd
import pandas as pd
import pyogrio
from branca.colormap import StepColormap
from shapely import force_2d, make_valid

from map_design import PSPS_SCALE


CODE_DIR = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = CODE_DIR / "data" / "psps"
DEFAULT_YEARS = (2024, 2025)
METRIC_FIELD = "sum_monthly_max_customer_events"
METRIC_LABEL = (
    "Sum of monthly maximum PSPS events affecting any one reported customer account"
)
REPORTS_PAGE = (
    "https://www.cpuc.ca.gov/consumer-support/psps/"
    "utility-company-psps-reports-post-event-and-post-season"
)

_METRIC_FIELDS = (
    "MaxEvents",
    "MaxHours",
    "MinHours",
    "MedHours",
    "TotCustomer",
    "TotHours",
    "TotCARE_Customer",
    "TotCARE_Hours",
    "TotMBL_Customer",
    "TotMBL_Hours",
    "TotSelfID_Customer",
    "TotSelfID_Hours",
)
_TRACT_FIELDS = ("GEOID", "Tract", "Track", "TRACT", "Tract_1", "TRACT2")


def load_source_manifest(data_dir: Path = DEFAULT_DATA_DIR) -> pd.DataFrame:
    """Return the explicit utility/year/source coverage table."""

    manifest = pd.read_csv(Path(data_dir) / "source_manifest.csv", dtype=str)
    manifest["year_numeric"] = pd.to_numeric(manifest["year"], errors="coerce")
    return manifest


def _gdb_path_in_zip(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        root = next(
            (
                member.split(".gdb/")[0] + ".gdb"
                for member in archive.namelist()
                if ".gdb/" in member
            ),
            None,
        )
    if root is None:
        raise ValueError(f"No file geodatabase found in {path}")
    return f"/vsizip/{path.resolve()}/{root}"


def _normalize_raw_geoid(value: object) -> Optional[str]:
    """Normalize full tract GEOIDs when a utility supplied one.

    Some sources store an 11-digit GEOID as a float, dropping California's
    leading zero. Local tract numbers (for example Liberty's ``1.02``) are not
    guessed; they are resolved spatially against Census geometry instead.
    """

    if pd.isna(value):
        return None
    text = str(value).strip()
    if re.fullmatch(r"\d+\.0+", text):
        text = text.split(".", 1)[0]
    if not text.isdigit():
        return None
    if len(text) == 10:
        text = text.zfill(11)
    return text if len(text) == 11 and text.startswith("06") else None


def load_california_tracts(data_dir: Path = DEFAULT_DATA_DIR) -> gpd.GeoDataFrame:
    """Load official 2010 Census TIGER/Line California tract polygons."""

    path = Path(data_dir) / "tl_2010_06_tract10.zip"
    if not path.exists():
        raise FileNotFoundError(
            f"Missing {path}. See the source URL in source_manifest.csv."
        )
    tracts = gpd.read_file(f"zip://{path.resolve()}")
    required = {"GEOID10", "NAMELSAD10", "geometry"}
    missing = required.difference(tracts.columns)
    if missing:
        raise ValueError(f"Census tract file missing fields: {sorted(missing)}")
    tracts = tracts[["GEOID10", "NAMELSAD10", "geometry"]].rename(
        columns={"GEOID10": "GEOID", "NAMELSAD10": "NAMELSAD"}
    )
    tracts["GEOID"] = tracts["GEOID"].astype(str)
    if tracts["GEOID"].duplicated().any() or len(tracts) != 8_057:
        raise ValueError("Unexpected California Census tract coverage")
    return tracts.to_crs("EPSG:4326")


def _read_spatial_submissions(
    data_dir: Path,
    years: Sequence[int],
) -> gpd.GeoDataFrame:
    manifest = load_source_manifest(data_dir)
    wanted = manifest[
        manifest["year_numeric"].isin(years)
        & manifest["submission_form"].eq("file_geodatabase")
    ]
    parts = []

    for row in wanted.itertuples(index=False):
        archive_path = Path(data_dir) / row.filename
        if not archive_path.exists():
            raise FileNotFoundError(f"Missing CPUC source file: {archive_path}")
        gdb_path = _gdb_path_in_zip(archive_path)
        candidate_layers = pyogrio.list_layers(gdb_path)
        found_data_layer = False

        for layer_name, _geometry_type in candidate_layers:
            # SCE's 2024 geodatabase also bundles a CES_FINAL reference layer
            # containing the same POSTSR2A fields and rows. It is not a second
            # PSPS submission and would double every SCE observation.
            if str(layer_name).casefold() == "ces_final":
                continue
            info = pyogrio.read_info(gdb_path, layer=layer_name)
            fields = set(info["fields"])
            if not {"YYYYMM", "MaxEvents"}.issubset(fields):
                continue
            found_data_layer = True
            frame = gpd.read_file(gdb_path, layer=layer_name)
            tract_field = next(
                (field for field in _TRACT_FIELDS if field in frame.columns),
                None,
            )
            if tract_field is None:
                raise ValueError(
                    f"{row.filename}/{layer_name} has no recognizable tract field"
                )

            keep = ["YYYYMM", tract_field, *_METRIC_FIELDS, "geometry"]
            keep = list(dict.fromkeys(column for column in keep if column in frame))
            frame = frame[keep].copy()
            frame = frame.rename(columns={tract_field: "source_tract"})
            frame["source_file"] = row.filename
            frame["source_layer"] = layer_name
            frame["utility"] = row.utility
            frame["report_year"] = int(row.year_numeric)
            frame["source_row"] = range(1, len(frame) + 1)
            frame["geometry"] = frame.geometry.map(
                lambda geom: (
                    make_valid(force_2d(geom))
                    if geom is not None and not force_2d(geom).is_valid
                    else force_2d(geom) if geom is not None else None
                )
            )
            frame = frame.to_crs("EPSG:4326")
            parts.append(frame)

        if not found_data_layer:
            raise ValueError(f"No POSTSR2A data layer found in {archive_path}")

    if not parts:
        raise ValueError("No spatial POSTSR2A submissions selected")

    records = gpd.GeoDataFrame(
        pd.concat(parts, ignore_index=True),
        geometry="geometry",
        crs="EPSG:4326",
    )
    records["YYYYMM"] = records["YYYYMM"].astype(str).str.replace(r"\.0$", "", regex=True)
    for field in _METRIC_FIELDS:
        if field in records:
            records[field] = pd.to_numeric(records[field], errors="coerce")

    wrong_year = records.loc[
        records["YYYYMM"].str[:4]
        != records["report_year"].astype(str)
    ]
    if len(wrong_year):
        raise ValueError(
            f"{len(wrong_year)} POSTSR2A rows have YYYYMM outside report year"
        )
    if records["MaxEvents"].isna().any() or (records["MaxEvents"] <= 0).any():
        raise ValueError("POSTSR2A impact rows must have positive MaxEvents")
    return records


def _assign_census_geoids(
    records: gpd.GeoDataFrame,
    tracts: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:
    """Resolve utility tract identifiers to canonical Census GEOIDs."""

    result = records.copy()
    result["source_geoid"] = result["source_tract"].map(_normalize_raw_geoid)
    canonical_geoids = set(tracts["GEOID"])
    result["source_geoid_is_2010"] = result["source_geoid"].isin(canonical_geoids)
    points = result[["geometry"]].copy()
    points["geometry"] = points.geometry.representative_point()
    located = gpd.sjoin(
        points,
        tracts[["GEOID", "geometry"]],
        how="left",
        predicate="within",
    )
    if located.index.duplicated().any():
        raise ValueError("A POSTSR2A representative point matched multiple tracts")
    result["spatial_geoid"] = located["GEOID"].reindex(result.index)

    result["GEOID"] = result["source_geoid"].where(
        result["source_geoid_is_2010"],
        result["spatial_geoid"],
    )
    result["geography_status"] = "utility_geoid_matches_2010_geography"
    result.loc[
        result["source_geoid"].isna() & result["spatial_geoid"].notna(),
        "geography_status",
    ] = "2010_geoid_assigned_from_submitted_geometry"
    result.loc[
        result["source_geoid"].notna()
        & ~result["source_geoid_is_2010"]
        & result["spatial_geoid"].notna(),
        "geography_status",
    ] = (
        "newer_utility_geoid_normalized_to_2010_by_submitted_geometry"
    )
    result.loc[result["GEOID"].isna(), "geography_status"] = (
        "unlocatable_null_geometry_and_tract"
    )
    return result


def load_psps_records(
    data_dir: Path = DEFAULT_DATA_DIR,
    years: Iterable[int] = DEFAULT_YEARS,
) -> gpd.GeoDataFrame:
    """Load normalized utility POSTSR2A records with canonical tract GEOIDs."""

    selected_years = tuple(sorted({int(year) for year in years}))
    if not selected_years:
        raise ValueError("At least one report year is required")
    tracts = load_california_tracts(data_dir)
    records = _read_spatial_submissions(Path(data_dir), selected_years)
    return _assign_census_geoids(records, tracts)


def load_psps_frequency_layer(
    data_dir: Path = DEFAULT_DATA_DIR,
    years: Iterable[int] = DEFAULT_YEARS,
) -> gpd.GeoDataFrame:
    """Return reported-impact tract polygons and a PSPS frequency proxy.

    ``sum_monthly_max_customer_events`` sums one maximum per normalized tract
    and month over the selected period. Duplicate source rows and overlaps
    between utility filings are collapsed with ``max``, not added. Geometry is
    the official 2010 Census tract polygon.
    """

    selected_years = tuple(sorted({int(year) for year in years}))
    records = load_psps_records(data_dir, selected_years)
    located = records.loc[records["GEOID"].notna()].copy()

    # Some submissions repeat a tract-month across event-window layers, and
    # utility territories can overlap. MaxEvents is already a monthly maximum,
    # so adding those rows would double count. Retain one maximum for each
    # normalized tract-month, then sum the monthly values through time.
    tract_month = (
        located.groupby(["GEOID", "report_year", "YYYYMM"], as_index=False)
        .agg(
            monthly_max_customer_events=("MaxEvents", "max"),
            source_records=("MaxEvents", "size"),
            reporting_utilities=(
                "utility",
                lambda values: ", ".join(sorted(set(values))),
            ),
        )
    )
    summary = (
        tract_month.groupby("GEOID", as_index=False)
        .agg(
            sum_monthly_max_customer_events=(
                "monthly_max_customer_events",
                "sum",
            ),
            max_monthly_max_customer_events=(
                "monthly_max_customer_events",
                "max",
            ),
            impacted_months=("YYYYMM", "nunique"),
            source_record_count=("source_records", "sum"),
            reporting_years=("report_year", lambda values: ", ".join(map(str, sorted(set(values))))),
            reporting_utilities=(
                "reporting_utilities",
                lambda values: ", ".join(
                    sorted(
                        {
                            utility
                            for combined in values
                            for utility in combined.split(", ")
                        }
                    )
                ),
            ),
        )
    )
    summary[METRIC_FIELD] = summary[METRIC_FIELD].astype("Int64")
    summary["max_monthly_max_customer_events"] = summary[
        "max_monthly_max_customer_events"
    ].astype("Int64")

    tracts = load_california_tracts(Path(data_dir))
    geography = tracts[tracts["GEOID"].isin(summary["GEOID"])].copy()
    status = (
        located.groupby("GEOID")["geography_status"]
        .agg(lambda values: "; ".join(sorted(set(values))))
        .rename("geography_status")
        .reset_index()
    )
    layer = geography.merge(summary, on="GEOID", validate="one_to_one")
    layer = layer.merge(status, on="GEOID", validate="one_to_one")
    layer = gpd.GeoDataFrame(layer, geometry="geometry", crs=located.crs)
    layer["tract_label"] = "Census tract " + layer["GEOID"].str[-6:]
    layer["tract_vintage"] = "2010 Census geography"
    layer["psps_data_status"] = "reported_psps_impact"
    layer["metric_period"] = f"{selected_years[0]}–{selected_years[-1]}"
    layer["metric_definition"] = METRIC_LABEL
    return layer


def validate_psps_layer(
    layer: gpd.GeoDataFrame,
    records: Optional[gpd.GeoDataFrame] = None,
) -> dict:
    """Return validation statistics and raise on unsafe output."""

    impacted = layer[layer[METRIC_FIELD].notna()]
    if layer.crs is None or layer.crs.to_epsg() != 4326:
        raise ValueError("PSPS layer must use EPSG:4326")
    if layer["GEOID"].duplicated().any():
        raise ValueError("PSPS layer has duplicate tract GEOIDs")
    if impacted.empty or (impacted[METRIC_FIELD] <= 0).any():
        raise ValueError("PSPS layer has no valid positive-impact tracts")
    if not impacted.geometry.is_valid.all():
        raise ValueError("PSPS layer contains invalid impacted tract geometry")
    if impacted.geometry.isna().any() or impacted.geometry.is_empty.any():
        raise ValueError("PSPS layer contains missing impacted tract geometry")

    result = {
        "reported_impact_tract_units": int(len(layer)),
        "tracts_with_reported_impact": int(len(impacted)),
        "metric_min": int(impacted[METRIC_FIELD].min()),
        "metric_max": int(impacted[METRIC_FIELD].max()),
        "metric_sum": int(impacted[METRIC_FIELD].sum()),
        "geometry_types": sorted(impacted.geometry.geom_type.unique().tolist()),
        "bounds_wgs84": [round(float(value), 5) for value in layer.total_bounds],
        "tract_vintage": "2010",
    }
    if records is not None:
        unlocated = records[records["GEOID"].isna()]
        result.update(
            {
                "source_records": int(len(records)),
                "located_source_records": int(records["GEOID"].notna().sum()),
                "unlocatable_source_records": int(len(unlocated)),
                "unlocatable_customer_accounts": int(
                    unlocated["TotCustomer"].fillna(0).sum()
                ),
            }
        )
    return result


def add_psps_frequency_layer(
    map_object: folium.Map,
    layer: Optional[gpd.GeoDataFrame] = None,
    *,
    data_dir: Path = DEFAULT_DATA_DIR,
    years: Iterable[int] = DEFAULT_YEARS,
    show: bool = False,
    show_unreported_context: bool = False,
    simplify_meters: float = 150,
    add_legend: bool = True,
    pane: Optional[str] = None,
) -> folium.FeatureGroup:
    """Add the PSPS frequency proxy to an existing Folium map."""

    if layer is None:
        layer = load_psps_frequency_layer(data_dir, years)
    display = layer.copy()
    if simplify_meters:
        projected = display.to_crs("EPSG:3310")
        projected["geometry"] = projected.geometry.simplify(
            simplify_meters,
            preserve_topology=True,
        )
        display = projected.to_crs("EPSG:4326")

    impacted_values = display[METRIC_FIELD].dropna()
    if impacted_values.empty:
        raise ValueError("No reported PSPS impact tracts to display")
    maximum = int(impacted_values.max())
    if maximum > PSPS_SCALE["observed_maximum"]:
        raise ValueError(
            f"PSPS value {maximum} exceeds the publication scale maximum "
            f"{PSPS_SCALE['observed_maximum']}"
        )
    breaks = [1, 2, 3, 5, 8, 12, 16]
    colors = [
        "#D9EEF7",
        "#C6E4F2",
        "#A7D3E8",
        "#7DB9D7",
        "#4B94BD",
        "#049834",
    ]
    color_scale = StepColormap(
        colors=colors,
        index=breaks,
        vmin=breaks[0],
        vmax=breaks[-1],
        caption=f"{METRIC_LABEL} ({display['metric_period'].iloc[0]})",
    )

    feature_group = folium.FeatureGroup(
        name=PSPS_SCALE["short_label"],
        show=show,
        overlay=True,
    )

    if show_unreported_context:
        context = load_california_tracts(data_dir)
        if simplify_meters:
            context_projected = context.to_crs("EPSG:3310")
            context_projected["geometry"] = context_projected.geometry.simplify(
                simplify_meters,
                preserve_topology=True,
            )
            context = context_projected.to_crs("EPSG:4326")
        folium.GeoJson(
            data=json.loads(context.to_json(drop_id=True)),
            name="California tracts — no impact/coverage inference",
            style_function=lambda _feature: {
                "fillColor": "#bdbdbd",
                "color": "#999999",
                "weight": 0.2,
                "fillOpacity": 0.12,
            },
            tooltip=folium.GeoJsonTooltip(
                fields=["NAMELSAD", "GEOID"],
                aliases=[
                    "Census tract:",
                    "GEOID:",
                ],
                sticky=False,
            ),
            pane=pane,
        ).add_to(feature_group)

    def style(feature: dict) -> dict:
        value = feature["properties"].get(METRIC_FIELD)
        pattern_index = next(
            (
                index
                for index, item in enumerate(PSPS_SCALE["classes"], start=1)
                if float(value) >= item["minimum"]
                and float(value) <= item["maximum"]
            ),
            len(PSPS_SCALE["classes"]),
        )
        return {
            "fillColor": f"url(#psps-pattern-{pattern_index})",
            "color": "#049834",
            "weight": 0.65,
            "fillOpacity": 1,
        }

    tooltip_fields = [
        "tract_label",
        "GEOID",
        "tract_vintage",
        METRIC_FIELD,
        "impacted_months",
        "reporting_years",
        "reporting_utilities",
        "psps_data_status",
    ]
    tooltip_aliases = [
        "Submitted tract:",
        "GEOID:",
        "Reporting geography:",
        f"{METRIC_LABEL}:",
        "Months with reported impact:",
        "Years with reported impact:",
        "Reporting utilities:",
        "Data status:",
    ]
    folium.GeoJson(
        data=json.loads(display.to_json(drop_id=True)),
        name="CPUC POSTSR2A tract records",
        style_function=style,
        highlight_function=lambda _feature: {
            "weight": 2,
            "color": "#0033CC",
        },
        tooltip=folium.GeoJsonTooltip(
            fields=tooltip_fields,
            aliases=tooltip_aliases,
            localize=True,
            sticky=False,
        ),
        pane=pane,
    ).add_to(feature_group)
    feature_group.add_to(map_object)
    if add_legend:
        color_scale.add_to(map_object)
    return feature_group


if __name__ == "__main__":
    records_frame = load_psps_records()
    layer_frame = load_psps_frequency_layer()
    print(json.dumps(validate_psps_layer(layer_frame, records_frame), indent=2))
