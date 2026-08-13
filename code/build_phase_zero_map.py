"""Rebuild the California data-center context map.

Run from the repository root:

    .venv/bin/python code/build_phase_zero_map.py
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import folium
import geopandas as gpd
import pandas as pd
from folium import (
    CircleMarker,
    DivIcon,
    FeatureGroup,
    GeoJson,
    GeoJsonPopup,
    Marker,
)
from folium.map import CustomPane
from folium.plugins import MarkerCluster
from shapely.geometry import Point

from diesel_pm_layer import load_diesel_pm_data
from lra_utility_layers import (
    add_lra_layer,
    add_utility_layer,
    load_lra,
    load_utility_territories,
    simplify_for_web,
)
from psps_frequency_layer import (
    METRIC_FIELD as PSPS_METRIC_FIELD,
    load_psps_frequency_layer,
)
from map_design import DESIGN_TOKENS, PROJECT_FIELD_LABELS
from map_ui import install_ui
from tpp_geometry import (
    SUBSTATION_SERVICE,
    add_phase_zero_reference_points,
    arcgis_to_gdf,
    build_upgrades,
)


CODE_DIR = Path(__file__).resolve().parent
TRANSMISSION_PATH = (
    CODE_DIR / "data" / "Transmission_Line_1899613689745579643.geojson"
)
TPP_PATH = CODE_DIR / "tpp_upgrades.csv"
TPP_PROJECTS_PATH = CODE_DIR / "tpp_projects.csv"
DATA_CENTER_PATH = CODE_DIR / "data" / "data_centers_corrected.csv"
SUBSTATION_SNAPSHOT_PATH = CODE_DIR / "data" / "substations_source.geojson"
SUBSTATION_MANIFEST_PATH = CODE_DIR / "data" / "substations_source_manifest.json"
DEFAULT_OUTPUT_DIR = CODE_DIR.parent / "dist"

DATA_CENTER_FIELD_LABELS = {
    field: label
    for field, label in PROJECT_FIELD_LABELS.items()
    if field not in {"Page Link", "Docket Link"}
}


def load_mappable_data_centers(
    path: Path = DATA_CENTER_PATH,
) -> tuple[pd.DataFrame, int]:
    """Load only documented project rows with valid California coordinates."""

    source = pd.read_csv(path)
    source["PROJECT_TYPE"] = "CEC SPPE data center"
    source["VERIFICATION_NOTE"] = ""
    project_mask = source["DOCKET NO. "].astype(str).str.fullmatch(
        r"\d{2}-SPPE-\d{2}",
        na=False,
    )
    projects = source.loc[project_mask].copy()
    total_projects = len(projects)
    for coordinate in ("LAT", "LONG"):
        cleaned = (
            projects[coordinate]
            .astype("string")
            .str.strip()
            .str.replace(r"[,\s]+$", "", regex=True)
        )
        projects[coordinate] = pd.to_numeric(cleaned, errors="coerce")
    projects = projects[
        projects["LAT"].between(32, 43)
        & projects["LONG"].between(-125, -113)
    ].copy()
    return projects, total_projects


def _data_center_popup(row: pd.Series) -> str:
    rows = []
    for field, label in DATA_CENTER_FIELD_LABELS.items():
        value = row.get(field, "")
        if pd.isna(value) or not str(value).strip():
            continue
        rows.append(
            f"<tr><th style='text-align:left;vertical-align:top;padding-right:8px'>"
            f"{html.escape(label)}</th><td>{html.escape(str(value))}</td></tr>"
        )
    links = []
    for field, label in (("Page Link", "CEC project page"), ("Docket Link", "Docket")):
        value = row.get(field, "")
        if pd.notna(value) and str(value).startswith("https://"):
            links.append(
                f"<a href='{html.escape(str(value), quote=True)}' "
                f"target='_blank' rel='noopener'>{label}</a>"
            )
    if links:
        rows.append(
            "<tr><th style='text-align:left;padding-right:8px'>Sources</th>"
            f"<td>{' · '.join(links)}</td></tr>"
        )
    return "<table>" + "".join(rows) + "</table>"


def enrich_data_centers(
    projects: pd.DataFrame,
    *,
    lra: gpd.GeoDataFrame,
    utilities: gpd.GeoDataFrame,
    diesel_pm: gpd.GeoDataFrame,
    psps_frequency: gpd.GeoDataFrame,
) -> pd.DataFrame:
    """Attach the map's contextual point-in-polygon values to each project."""

    result = projects.copy()
    context_rows = []
    for _, row in result.iterrows():
        point = Point(float(row["LONG"]), float(row["LAT"]))
        lra_matches = sorted(
            set(lra.loc[lra.intersects(point), "lra_name"].dropna().astype(str))
        )
        utility_matches = sorted(
            set(
                utilities.loc[
                    utilities.intersects(point), "utility_name"
                ].dropna().astype(str)
            )
        )
        diesel_matches = diesel_pm.loc[diesel_pm.intersects(point)]
        psps_matches = psps_frequency.loc[psps_frequency.intersects(point)]

        diesel_percentile = (
            float(diesel_matches["diesel_pm_percentile"].iloc[0])
            if len(diesel_matches)
            and pd.notna(diesel_matches["diesel_pm_percentile"].iloc[0])
            else pd.NA
        )
        psps_value = (
            int(psps_matches[PSPS_METRIC_FIELD].max())
            if len(psps_matches)
            else pd.NA
        )
        context_rows.append(
            {
                "map_lra": ", ".join(lra_matches) if lra_matches else "Outside published LRA polygons",
                "map_distribution_utility": (
                    ", ".join(utility_matches)
                    if utility_matches
                    else "No published distribution-area match"
                ),
                "map_diesel_pm_percentile": (
                    round(diesel_percentile, 1)
                    if pd.notna(diesel_percentile)
                    else pd.NA
                ),
                "map_diesel_pm_top_quintile": (
                    "Yes"
                    if pd.notna(diesel_percentile) and diesel_percentile >= 80
                    else "No"
                    if pd.notna(diesel_percentile)
                    else "Missing"
                ),
                "map_psps_frequency": psps_value,
                "map_psps_status": (
                    "Reported-impact tract record"
                    if pd.notna(psps_value)
                    else "No reported-impact record mapped; not treated as zero"
                ),
            }
        )
    context = pd.DataFrame(context_rows, index=result.index)
    return pd.concat([result, context], axis=1)


def _transmission_style(weight: float, opacity: float):
    color = DESIGN_TOKENS["color"]["transmission"]

    def style(_feature):
        return {"color": color, "weight": weight, "opacity": opacity}

    return style


def _upgrade_line_style(feature):
    properties = feature["properties"]
    is_new_line = properties.get("upgrade_type") == "new_line"
    color = (
        DESIGN_TOKENS["color"]["tpp_new"]
        if is_new_line
        else DESIGN_TOKENS["color"]["tpp"]
    )
    return {
        "color": color,
        "weight": 4 if is_new_line else 3,
        "opacity": 0.86,
        "dashArray": "10 6" if is_new_line else None,
    }


def _display_number(value: object) -> str:
    number = pd.to_numeric(value, errors="coerce")
    if pd.isna(number):
        return ""
    return f"{float(number):g}"


def _tpp_popup_html(row) -> str:
    """Render the intentionally concise public-facing TPP project metadata."""

    metadata = [
        ("kV", _display_number(row["kV"])),
        ("Approx. miles", _display_number(row["approx_miles"])),
        ("Cost", row["project_cost"]),
    ]
    metadata_html = "".join(
        "<div class='map-app-tpp-card__metric'>"
        f"<dt>{html.escape(label)}</dt>"
        f"<dd>{html.escape(str(value))}</dd>"
        "</div>"
        for label, value in metadata
        if str(value).strip()
    )
    description = html.escape(str(row["notes"])).replace("\n", "<br>")
    return (
        "<article class='map-app-tpp-card'>"
        "<p class='map-app-tpp-card__eyebrow'>Transmission project</p>"
        f"<h3 class='map-app-tpp-card__title'>"
        f"{html.escape(str(row['project_name']))}</h3>"
        "<section class='map-app-tpp-card__description'>"
        "<h4>Project description</h4>"
        f"<p>{description}</p>"
        "</section>"
        f"<dl class='map-app-tpp-card__metrics'>{metadata_html}</dl>"
        "</article>"
    )


def _write_web_geojson(
    frame: gpd.GeoDataFrame,
    *,
    filename: str,
    fields: list[str],
    simplify_meters: float = 0,
    web_data_dir: Path,
) -> str:
    """Write GeoJSON plus a file-URL-safe lazy-loading companion asset."""

    display = frame[fields + ["geometry"]].copy()
    if display.crs is None:
        display = display.set_crs("EPSG:4326")
    elif display.crs.to_epsg() != 4326:
        display = display.to_crs("EPSG:4326")
    if simplify_meters:
        projected = display.to_crs("EPSG:3310")
        projected.geometry = projected.geometry.simplify(
            simplify_meters,
            preserve_topology=True,
        )
        display = projected.to_crs("EPSG:4326")
    web_data_dir.mkdir(parents=True, exist_ok=True)
    path = web_data_dir / filename
    payload = display.to_json(drop_id=True)
    path.write_text(payload, encoding="utf-8")
    layer_id = path.stem
    script_path = path.with_suffix(".js")
    script_path.write_text(
        (
            "window.__MAP_APP_LAYER_DATA__="
            "window.__MAP_APP_LAYER_DATA__||{};"
            f"window.__MAP_APP_LAYER_DATA__[{json.dumps(layer_id)}]="
            f"{payload};"
        ),
        encoding="utf-8",
    )
    return f"data/web/{filename}"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def refresh_substation_snapshot() -> gpd.GeoDataFrame:
    """Refresh the reviewed CEC snapshot only when explicitly requested."""

    substations = arcgis_to_gdf(SUBSTATION_SERVICE)
    required = {"Name", "Max_Voltag", "Owner", "COUNTY", "Status", "geometry"}
    missing = required.difference(substations.columns)
    if missing or len(substations) < 4_000:
        raise RuntimeError(
            "CEC substation refresh failed completeness checks: "
            f"{len(substations):,} features; missing fields {sorted(missing)}"
        )
    SUBSTATION_SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    SUBSTATION_SNAPSHOT_PATH.write_text(
        substations.to_json(drop_id=True), encoding="utf-8"
    )
    manifest = {
        "source_url": SUBSTATION_SERVICE,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "feature_count": len(substations),
        "sha256": _sha256(SUBSTATION_SNAPSHOT_PATH),
    }
    SUBSTATION_MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return substations


def load_substation_snapshot() -> gpd.GeoDataFrame:
    """Load and verify the committed CEC snapshot without network fallback."""

    if not SUBSTATION_SNAPSHOT_PATH.exists() or not SUBSTATION_MANIFEST_PATH.exists():
        raise FileNotFoundError(
            "The committed substation snapshot or its manifest is missing. "
            "Run with --refresh-substations to create a reviewed replacement."
        )
    manifest = json.loads(SUBSTATION_MANIFEST_PATH.read_text(encoding="utf-8"))
    actual_hash = _sha256(SUBSTATION_SNAPSHOT_PATH)
    if actual_hash != manifest.get("sha256"):
        raise RuntimeError("Substation snapshot SHA-256 does not match its manifest")
    substations = gpd.read_file(SUBSTATION_SNAPSHOT_PATH)
    if len(substations) != manifest.get("feature_count") or substations.empty:
        raise RuntimeError("Substation snapshot feature count is malformed")
    required = {"Name", "Max_Voltag", "Owner", "COUNTY", "Status", "geometry"}
    missing = required.difference(substations.columns)
    if missing or substations.geometry.isna().any():
        raise RuntimeError(f"Substation snapshot is missing required data: {sorted(missing)}")
    return substations


def build_map(*, output_dir: Path = DEFAULT_OUTPUT_DIR, refresh_substations: bool = False):
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    web_data_dir = output_dir / "data" / "web"
    substations = (
        refresh_substation_snapshot() if refresh_substations else load_substation_snapshot()
    )
    cec_substation_count = len(substations)
    substations = add_phase_zero_reference_points(substations)

    transmission = gpd.read_file(TRANSMISSION_PATH)
    transmission["kV"] = pd.to_numeric(
        transmission["kV"], errors="coerce"
    ).fillna(0)

    upgrades = build_upgrades(
        TPP_PATH,
        substations,
        transmission,
        manifest_path=TPP_PROJECTS_PATH,
    )
    tpp_project_count = int(upgrades["project_name"].nunique())
    lra = simplify_for_web(load_lra(), tolerance_m=100)
    utilities = simplify_for_web(
        load_utility_territories(iou_only=True),
        tolerance_m=100,
    )
    diesel_pm = load_diesel_pm_data()
    psps_frequency = load_psps_frequency_layer()
    data_centers, total_data_center_projects = load_mappable_data_centers()
    data_centers = enrich_data_centers(
        data_centers,
        lra=lra,
        utilities=utilities,
        diesel_pm=diesel_pm,
        psps_frequency=psps_frequency,
    )

    map_object = folium.Map(
        location=[37.25, -119.45],
        zoom_start=6.5,
        zoom_snap=0.5,
        zoom_delta=0.5,
        wheel_px_per_zoom_level=120,
        tiles="CartoDB positron",
        control_scale=True,
    )
    map_object.get_root().header.add_child(
        folium.Element(
            """
            <style>
                /* Soft-gray hybrid: mute only the basemap, never analytical layers. */
                .leaflet-tile-pane {
                    filter: brightness(0.82) saturate(0.50) contrast(0.92);
                }
            </style>
            """
        )
    )
    pane_indices = DESIGN_TOKENS["pane_z_index"]
    for pane_name, token_name, pointer_events in (
        ("utility-polygons", "utility", True),
        ("diesel-polygons", "diesel", True),
        ("psps-patterns", "psps", True),
        ("lra-boundaries", "lra", True),
        ("grid-lines", "grid_lines", True),
        ("grid-points", "grid_points", True),
        ("data-centers", "data_centers", True),
    ):
        CustomPane(
            pane_name,
            z_index=pane_indices[token_name],
            pointer_events=pointer_events,
        ).add_to(map_object)

    data_center_layer = FeatureGroup(
        name=(
            f"CEC SPPE data centers ({len(data_centers)} mapped)"
        ),
        show=True,
        overlay=True,
    )
    data_center_cluster = MarkerCluster(
        name="Proposed data center clusters",
        show_coverage_on_hover=False,
        zoom_to_bounds_on_click=True,
        spiderfy_on_max_zoom=True,
        disable_clustering_at_zoom=16,
        max_cluster_radius=34,
        cluster_pane="data-centers",
        icon_create_function="""
function(cluster) {
  return L.divIcon({
    html: '<span class="map-app-cluster__count">' +
      cluster.getChildCount() + '</span>',
    className: 'map-app-cluster',
    iconSize: L.point(42, 42)
  });
}
""",
    )
    data_center_cluster.add_to(data_center_layer)
    data_center_markers = []
    for _, row in data_centers.iterrows():
        marker = Marker(
            [float(row["LAT"]), float(row["LONG"])],
            icon=DivIcon(
                icon_size=(30, 40),
                icon_anchor=(15, 38),
                class_name="map-app-pin-shell",
                html=(
                    '<span class="map-app-pin" aria-hidden="true">'
                    '<span class="map-app-pin__core"></span></span>'
                ),
            ),
            tooltip=folium.Tooltip(
                (
                    "<div class='map-app-tooltip__title'>"
                    f"{html.escape(str(row['PROJECT_NAME']))}</div>"
                    "<div class='map-app-tooltip__meta'>"
                    f"{html.escape(str(row.get('CITY', '')))} · "
                    f"{html.escape(str(row.get('PROJECT_STATUS', '')))} · "
                    f"{html.escape(str(row.get('PROJECT_TYPE', '')))}"
                    "</div>"
                ),
                sticky=False,
            ),
            pane="data-centers",
            rise_on_hover=True,
            rise_offset=300,
        )
        marker.add_to(data_center_cluster)
        data_center_markers.append(marker)
    data_center_layer.add_to(map_object)

    substation_layer = FeatureGroup(
        name="Substations",
        show=False,
        overlay=True,
    )
    substation_display = substations[
        ["Name", "Max_Voltag", "Owner", "COUNTY", "Status", "geometry"]
    ].copy()
    substation_layer.add_to(map_object)

    transmission_display = transmission[
        ["Name", "kV", "Owner", "Status", "geometry"]
    ].copy()

    def transmission_group(name):
        group = FeatureGroup(name=name, show=False, overlay=True)
        group.add_to(map_object)
        return group

    transmission_high_layer = transmission_group(
        "Existing transmission — 230 kV and above",
    )
    transmission_medium_layer = transmission_group(
        "Existing transmission — 115–229 kV",
    )
    transmission_low_layer = transmission_group(
        "Existing transmission — below 115 kV",
    )

    upgrade_group = FeatureGroup(name="Proposed Upgrades", show=True)
    lines = upgrades[
        upgrades.geometry.geom_type.isin(
            ["LineString", "MultiLineString", "GeometryCollection"]
        )
    ]
    points = upgrades[upgrades.geometry.geom_type == "Point"]

    lines = lines.copy()
    lines["popup_html"] = lines.apply(_tpp_popup_html, axis=1)
    popup_lines = lines[["popup_html", "upgrade_type", "geometry"]].copy()
    styled_lines = lines[["upgrade_type", "geometry"]].copy()
    tpp_popup = GeoJsonPopup(
        fields=["popup_html"],
        labels=False,
        class_name="map-app-tpp-popup",
        localize=False,
        max_width=520,
    )
    GeoJson(
        popup_lines,
        style_function=lambda feature: {
            "color": (
                DESIGN_TOKENS["color"]["tpp_new"]
                if feature["properties"].get("upgrade_type") == "new_line"
                else DESIGN_TOKENS["color"]["tpp"]
            ),
            "weight": 18,
            "opacity": 0.001,
        },
        highlight_function=lambda feature: {
            "color": (
                DESIGN_TOKENS["color"]["tpp_new"]
                if feature["properties"].get("upgrade_type") == "new_line"
                else DESIGN_TOKENS["color"]["tpp"]
            ),
            "weight": 18,
            "opacity": 0.16,
        },
        popup=tpp_popup,
        pane="grid-lines",
    ).add_to(upgrade_group)
    GeoJson(
        styled_lines,
        style_function=_upgrade_line_style,
        pane="grid-lines",
        interactive=False,
    ).add_to(upgrade_group)

    point_groups = points.assign(
        _coordinate_key=points.geometry.map(
            lambda point: (round(point.x, 7), round(point.y, 7))
        )
    ).groupby("_coordinate_key", sort=False)
    for _, point_group in point_groups:
        row = point_group.iloc[0]
        is_new = row["upgrade_type"] == "new_substation"
        is_reference = row["upgrade_type"] == "project_scope_reference"
        if len(point_group) > 1:
            point_class = "map-app-tpp-point--stacked"
        elif is_new:
            point_class = "map-app-tpp-point--new"
        elif is_reference:
            point_class = "map-app-tpp-point--reference"
        else:
            point_class = "map-app-tpp-point--upgrade"
        popup_html = "".join(
            (
                "<section class='map-app-tpp-point-record'>"
                + _tpp_popup_html(item)
                + "</section>"
            )
            for _, item in point_group.iterrows()
        )
        count_badge = (
            f"<span class='map-app-tpp-point__count'>{len(point_group)}</span>"
            if len(point_group) > 1
            else ""
        )
        tooltip = (
            f"{len(point_group)} CAISO upgrades at this location"
            if len(point_group) > 1
            else row["project_name"]
        )
        Marker(
            [row.geometry.y, row.geometry.x],
            tooltip=tooltip,
            popup=folium.Popup(popup_html, max_width=520),
            icon=DivIcon(
                html=(
                    f'<div class="map-app-tpp-point {point_class}">'
                    f"{count_badge}</div>"
                ),
                icon_size=(24, 24),
                icon_anchor=(12, 12),
            ),
            pane="grid-points",
        ).add_to(upgrade_group)

    upgrade_group.add_to(map_object)

    lra_layer = add_lra_layer(
        map_object,
        frame=lra,
        show=False,
        pane="lra-boundaries",
    )
    utility_layer = add_utility_layer(
        map_object,
        frame=utilities,
        distribution_only=True,
        iou_only=True,
        show=False,
        pane="utility-polygons",
    )
    diesel_percentile_layer = FeatureGroup(
        name="CES 5.0 diesel PM percentile",
        show=False,
        overlay=True,
    )
    diesel_percentile_layer.add_to(map_object)
    diesel_top_quintile_layer = FeatureGroup(
        name="CES 5.0 diesel PM top quintile (≥80)",
        show=False,
        overlay=True,
    )
    diesel_top_quintile_layer.add_to(map_object)
    psps_layer = FeatureGroup(
        name="Reported PSPS frequency, 2024–2025",
        show=False,
        overlay=True,
    )
    psps_layer.add_to(map_object)

    layer_registry = {
        "data_centers": data_center_layer,
        "tpp_upgrades": upgrade_group,
        "transmission_high": transmission_high_layer,
        "transmission_medium": transmission_medium_layer,
        "transmission_low": transmission_low_layer,
        "substations": substation_layer,
        "lra": lra_layer,
        "iou_territories": utility_layer,
        "diesel_percentile": diesel_percentile_layer,
        "diesel_top_quintile": diesel_top_quintile_layer,
        "psps_frequency": psps_layer,
    }
    transmission_tooltip = [
        {"field": "Name", "label": "Line:"},
        {"field": "kV", "label": "kV:"},
        {"field": "Owner", "label": "Owner:"},
        {"field": "Status", "label": "Status:"},
    ]
    lazy_layers = {
        "substations": {
            "url": _write_web_geojson(
                substation_display,
                filename="substations.geojson",
                fields=["Name", "Max_Voltag", "Owner", "COUNTY", "Status"],
                web_data_dir=web_data_dir,
            ),
            "kind": "substations",
            "pane": "grid-points",
            "color": DESIGN_TOKENS["color"]["substation"],
            "tooltip": [
                {"field": "Name", "label": "Substation:"},
                {"field": "Max_Voltag", "label": "Max kV:"},
                {"field": "Owner", "label": "Owner:"},
                {"field": "COUNTY", "label": "County:"},
                {"field": "Status", "label": "Status:"},
            ],
        },
        "transmission_high": {
            "url": _write_web_geojson(
                transmission_display[transmission_display["kV"].ge(230)],
                filename="transmission_high.geojson",
                fields=["Name", "kV", "Owner", "Status"],
                simplify_meters=40,
                web_data_dir=web_data_dir,
            ),
            "kind": "transmission",
            "pane": "grid-lines",
            "color": DESIGN_TOKENS["color"]["transmission"],
            "weight": 4,
            "opacity": 0.68,
            "tooltip": transmission_tooltip,
        },
        "transmission_medium": {
            "url": _write_web_geojson(
                transmission_display[
                    transmission_display["kV"].ge(115)
                    & transmission_display["kV"].lt(230)
                ],
                filename="transmission_medium.geojson",
                fields=["Name", "kV", "Owner", "Status"],
                simplify_meters=40,
                web_data_dir=web_data_dir,
            ),
            "kind": "transmission",
            "pane": "grid-lines",
            "color": DESIGN_TOKENS["color"]["transmission"],
            "weight": 2.25,
            "opacity": 0.48,
            "tooltip": transmission_tooltip,
        },
        "transmission_low": {
            "url": _write_web_geojson(
                transmission_display[transmission_display["kV"].lt(115)],
                filename="transmission_low.geojson",
                fields=["Name", "kV", "Owner", "Status"],
                simplify_meters=40,
                web_data_dir=web_data_dir,
            ),
            "kind": "transmission",
            "pane": "grid-lines",
            "color": DESIGN_TOKENS["color"]["transmission"],
            "weight": 1,
            "opacity": 0.32,
            "tooltip": transmission_tooltip,
        },
        "diesel_percentile": {
            "url": _write_web_geojson(
                diesel_pm,
                filename="diesel_percentile.geojson",
                fields=[
                    "tract_geoid",
                    "county",
                    "approximate_location",
                    "diesel_pm_tons_per_year",
                    "diesel_pm_percentile",
                    "diesel_pm_status",
                ],
                simplify_meters=100,
                web_data_dir=web_data_dir,
            ),
            "kind": "diesel_percentile",
            "pane": "diesel-polygons",
            "tooltip": [
                {"field": "county", "label": "County:"},
                {"field": "approximate_location", "label": "Location:"},
                {
                    "field": "diesel_pm_tons_per_year",
                    "label": "Diesel PM (tons/year):",
                },
                {"field": "diesel_pm_percentile", "label": "Percentile:"},
                {"field": "diesel_pm_status", "label": "Data status:"},
            ],
        },
        "diesel_top_quintile": {
            "url": _write_web_geojson(
                diesel_pm[
                    diesel_pm["diesel_pm_percentile"].ge(80).fillna(False)
                ],
                filename="diesel_top_quintile.geojson",
                fields=[
                    "tract_geoid",
                    "county",
                    "approximate_location",
                    "diesel_pm_tons_per_year",
                    "diesel_pm_percentile",
                    "diesel_pm_status",
                ],
                simplify_meters=100,
                web_data_dir=web_data_dir,
            ),
            "kind": "diesel_top_quintile",
            "pane": "diesel-polygons",
            "tooltip": [
                {"field": "county", "label": "County:"},
                {"field": "approximate_location", "label": "Location:"},
                {"field": "diesel_pm_percentile", "label": "Percentile:"},
            ],
        },
        "psps_frequency": {
            "url": _write_web_geojson(
                psps_frequency,
                filename="psps_frequency.geojson",
                fields=[
                    "tract_label",
                    "GEOID",
                    "tract_vintage",
                    PSPS_METRIC_FIELD,
                    "impacted_months",
                    "reporting_years",
                    "reporting_utilities",
                    "psps_data_status",
                ],
                simplify_meters=150,
                web_data_dir=web_data_dir,
            ),
            "kind": "psps",
            "pane": "psps-patterns",
            "tooltip": [
                {"field": "tract_label", "label": "Submitted tract:"},
                {"field": "GEOID", "label": "GEOID:"},
                {
                    "field": PSPS_METRIC_FIELD,
                    "label": "Reported PSPS frequency:",
                },
                {"field": "impacted_months", "label": "Impacted months:"},
                {"field": "reporting_years", "label": "Reporting years:"},
                {"field": "reporting_utilities", "label": "Utilities:"},
                {"field": "psps_data_status", "label": "Data status:"},
            ],
        },
    }
    for lazy_config in lazy_layers.values():
        lazy_config["script_url"] = str(lazy_config["url"]).replace(
            ".geojson", ".js"
        )
    install_ui(
        map_object,
        layer_registry=layer_registry,
        projects=data_centers,
        data_center_markers=data_center_markers,
        lazy_layers=lazy_layers,
        tpp_summary={
            "projects": int(upgrades["project_id"].nunique()),
            "components": int(len(upgrades)),
        },
    )
    map_object.get_root().header.add_child(
        folium.Element(
            "<title>California Data Centers, Grid & Community Context</title>"
        )
    )
    output_path = output_dir / "index.html"
    map_object.save(output_path)
    output_html = output_path.read_text(encoding="utf-8")
    output_html = output_html.replace("<html>", '<html lang="en">', 1)
    output_html = re.sub(
        r'<meta name="viewport" content="width=device-width,\s*'
        r'initial-scale=1\.0, maximum-scale=1\.0, user-scalable=no" />',
        '<meta name="viewport" content="width=device-width, initial-scale=1.0" />',
        output_html,
        count=1,
    )
    forbidden = ("file://", "localhost", str(CODE_DIR.parent.resolve()))
    found = [value for value in forbidden if value in output_html]
    if found:
        raise RuntimeError(f"Generated HTML contains forbidden paths: {found}")
    output_path.write_text(output_html, encoding="utf-8")
    (output_dir / ".nojekyll").touch()

    print(f"Loaded {cec_substation_count:,} CEC substations from snapshot")
    print(
        f"Mapped {len(data_centers)} / {total_data_center_projects} "
        "data-center records with documented coordinates"
    )
    print(f"Built {len(upgrades)} / {len(pd.read_csv(TPP_PATH))} TPP row geometries")
    print(upgrades["upgrade_type"].value_counts().to_string())
    print(f"Loaded {len(lra)} current Local Reliability Areas")
    print(f"Loaded {len(utilities)} IOU service territories")
    print(
        f"Loaded {len(diesel_pm):,} CalEnviroScreen tracts "
        f"({int(diesel_pm['diesel_pm_top_quintile'].fillna(False).sum()):,} "
        "in the diesel-PM top quintile)"
    )
    print(
        f"Loaded {int(psps_frequency[PSPS_METRIC_FIELD].notna().sum()):,} "
        "tracts with reported 2024–2025 PSPS impact"
    )
    print(f"Saved {output_path}")
    return map_object, substations, transmission, upgrades


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Site output directory (default: dist)",
    )
    parser.add_argument(
        "--refresh-substations",
        action="store_true",
        help="Explicitly download and replace the committed CEC snapshot",
    )
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    build_map(
        output_dir=arguments.output_dir,
        refresh_substations=arguments.refresh_substations,
    )
