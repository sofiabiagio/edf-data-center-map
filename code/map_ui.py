"""Install the publication interface around the generated Folium map."""

from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Mapping, Optional, Sequence

import folium
import pandas as pd

from map_design import (
    DESIGN_TOKENS,
    DIESEL_PM_SCALE,
    GUIDED_VIEWS,
    LAYER_METADATA,
    PROJECT_FIELD_LABELS,
    PROJECT_FIELDS_BY_VIEW,
    PSPS_SCALE,
    validate_design_config,
)


UI_DIR = Path(__file__).resolve().parent / "ui"
UI_CSS_PATH = UI_DIR / "map.css"
UI_JS_PATH = UI_DIR / "map.js"

IDENTITY_FIELDS = (
    "PROJECT_OWNER",
    "EXPECTED_COMPLETION",
)

LAYER_CATEGORIES = (
    {
        "id": "projects",
        "label": "Projects",
        "layers": ("data_centers",),
    },
    {
        "id": "grid",
        "label": "Grid infrastructure",
        "layers": (
            "tpp_upgrades",
            "transmission_high",
            "transmission_medium",
            "transmission_low",
            "substations",
        ),
    },
    {
        "id": "reliability",
        "label": "Reliability & jurisdiction",
        "layers": ("lra", "iou_territories"),
    },
    {
        "id": "context",
        "label": "Environmental & outage context",
        "layers": (
            "diesel_percentile",
            "diesel_top_quintile",
            "psps_frequency",
        ),
    },
)


def _json_safe(value):
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def stable_project_id(row: pd.Series) -> str:
    """Return a deterministic URL-safe project identifier."""

    explicit_value = row.get("PROJECT_ID", "")
    explicit_id = (
        str(explicit_value).strip()
        if explicit_value is not None and not pd.isna(explicit_value)
        else ""
    )
    docket = str(row.get("DOCKET NO. ", "")).strip()
    source = explicit_id or docket or str(row.get("PROJECT_NAME", "project")).strip()
    slug = re.sub(r"[^a-z0-9]+", "-", source.lower()).strip("-")
    return slug or "project"


def serialize_projects(
    projects: pd.DataFrame,
    marker_names: Sequence[str],
) -> list[dict]:
    """Serialize project records without allowing source HTML into the page."""

    if len(projects) != len(marker_names):
        raise ValueError("Every mapped project must have one marker reference")
    records = []
    seen_ids = set()
    for marker_name, (_, row) in zip(marker_names, projects.iterrows()):
        project_id = stable_project_id(row)
        if project_id in seen_ids:
            raise ValueError(f"Duplicate stable project ID: {project_id}")
        seen_ids.add(project_id)
        fields = {
            field: _json_safe(row.get(field))
            for field in PROJECT_FIELD_LABELS
            if field not in {"Page Link", "Docket Link"}
        }
        sources = []
        for field, label in (
            ("Page Link", "CEC project page"),
            ("Docket Link", "CEC docket"),
        ):
            value = _json_safe(row.get(field))
            if isinstance(value, str) and value.startswith("https://"):
                sources.append({"label": label, "url": value})
        records.append(
            {
                "marker_name": marker_name,
                "project": {
                    "id": project_id,
                    "name": str(row["PROJECT_NAME"]).strip(),
                    "fields": fields,
                    "sources": sources,
                },
            }
        )
    return records


def _class_items(scale: Mapping, *, pattern: bool = False) -> list[dict]:
    items = []
    for entry in scale["classes"]:
        item = {"label": entry["label"]}
        if pattern:
            item["pattern"] = DESIGN_TOKENS["color"]["psps"]
        else:
            item["color"] = entry["color"]
        items.append(item)
    return items


def _legend_config(tpp_summary: Optional[Mapping[str, int]] = None) -> dict[str, dict]:
    color = DESIGN_TOKENS["color"]
    psps_note = " ".join(
        [
            PSPS_SCALE["method"],
            PSPS_SCALE["limitations"],
            PSPS_SCALE["missing_copy"],
        ]
    )
    return {
        "data_centers": {
            "type": "classes",
            "title": "Proposed data centers",
            "items": [
                {
                    "label": "Documented project location",
                    "symbol_kind": "data-center",
                },
                {
                    "label": "Cluster · number is project count",
                    "symbol_kind": "data-center-cluster",
                },
            ],
        },
        "tpp_upgrades": {
            "type": "classes",
            "title": "CAISO transmission plan upgrades",
            "summary": (
                f"{tpp_summary['projects']} approved projects · "
                f"{tpp_summary['components']} mapped components"
                if tpp_summary
                else "38 approved projects"
            ),
            "items": [
                {
                    "label": "Work on an existing line",
                    "color": color["tpp"],
                    "line": True,
                    "line_case": "existing-line-work",
                },
                {
                    "label": "Build a new line",
                    "color": color["tpp_new"],
                    "line": True,
                    "dashed": True,
                    "line_case": "new-line-work",
                },
                {
                    "label": "Existing-substation upgrade",
                    "color": color["tpp"],
                    "symbol_kind": "substation-upgrade",
                },
                {
                    "label": "New substation · approximate location",
                    "color": color["tpp_new_substation"],
                    "symbol_kind": "new-substation",
                },
                {
                    "label": "Multiple upgrades at one location · number is count",
                    "color": color["tpp"],
                    "symbol_kind": "coincident-upgrades",
                },
            ],
            "note_display": "visible",
            "note": (
                "Line styling indicates project type, not route precision. "
                "Some locations are schematic connectors or approximate "
                "segments rather than surveyed rights-of-way."
            ),
        },
        "transmission_high": {
            "type": "simple",
            "group": "existing_transmission",
            "title": "Existing transmission",
            "label": "Thick line — 230 kV and above",
        },
        "transmission_medium": {
            "type": "simple",
            "group": "existing_transmission",
            "title": "Existing transmission",
            "label": "Medium line — 115–229 kV",
        },
        "transmission_low": {
            "type": "simple",
            "group": "existing_transmission",
            "title": "Existing transmission",
            "label": "Thin line — below 115 kV",
        },
        "substations": {
            "type": "simple",
            "title": "Existing substations",
            "label": "Existing substation · visible at zoom 10+",
        },
        "lra": {
            "type": "simple",
            "title": "Local Reliability Areas",
            "label": "CAISO local-capacity study boundary",
            "note": (
                "An LRA is a reliability study area, not a direct measure of "
                "congestion, outage probability, or spare capacity."
            ),
        },
        "iou_territories": {
            "type": "classes",
            "title": "IOU service territories",
            "items": [
                {"label": "PG&E", "color": "#007C78"},
                {"label": "Southern California Edison", "color": "#B7791F"},
                {"label": "San Diego Gas & Electric", "color": "#2B6CB0"},
                {"label": "PacifiCorp", "color": "#6B46C1"},
                {"label": "Liberty Utilities", "color": "#A61B5B"},
                {"label": "Bear Valley Electric Service", "color": "#4A5568"},
            ],
            "note": (
                "CEC boundaries are approximate. Verify the serving utility "
                "for a specific site from project records or the utility."
            ),
        },
        "diesel_percentile": {
            "type": "classes",
            "title": DIESEL_PM_SCALE["short_label"],
            "items": _class_items(DIESEL_PM_SCALE),
            "range": "0–100 percentile · top quintile begins at 80",
            "note": DIESEL_PM_SCALE["interpretation"],
        },
        "diesel_top_quintile": {
            "type": "classes",
            "title": "Diesel PM top quintile",
            "items": [
                {
                    "label": "80th–100th percentile",
                    "color": "#54278F",
                }
            ],
            "note": DIESEL_PM_SCALE["interpretation"],
        },
        "psps_frequency": {
            "type": "classes",
            "title": PSPS_SCALE["short_label"],
            "items": _class_items(PSPS_SCALE, pattern=True),
            "range": (
                f"Observed mapped range: {PSPS_SCALE['observed_minimum']}–"
                f"{PSPS_SCALE['observed_maximum']}"
            ),
            "missing": (
                "No hatch · no reported-impact record mapped; coverage not "
                "established (not zero)"
            ),
            "note": psps_note,
        },
    }


def browser_config(tpp_summary: Optional[Mapping[str, int]] = None) -> dict:
    """Return the exact UI contract used by the runtime and legends."""

    validate_design_config()
    legends = _legend_config(tpp_summary)
    layers = {}
    for layer_id, metadata in LAYER_METADATA.items():
        layers[layer_id] = {
            "label": metadata["label"],
            "category": metadata["category"],
            "family": metadata.get("exclusive_family"),
            "min_zoom": metadata.get("semantic_min_zoom"),
            "legend": legends[layer_id],
        }
    views = {}
    for view_id, view in GUIDED_VIEWS.items():
        views[view_id] = {
            "label": view["label"],
            "question": view["question"],
            "layers": list(view["layers"]),
            "detail_fields": [
                field
                for field in PROJECT_FIELDS_BY_VIEW[view_id]
                if field != "PROJECT_NAME"
            ],
            "detail_intro": view["question"],
        }
    return {
        "default_view": "overview",
        "initial_view": {"center": [37.25, -119.45], "zoom": 6.5},
        "tokens": {
            "ink": DESIGN_TOKENS["color"]["ink"],
            "data_center": DESIGN_TOKENS["color"]["data_center_fill"],
            "data_center_edge": DESIGN_TOKENS["color"]["data_center_edge"],
        },
        "layers": layers,
        "views": views,
        "layer_categories": [
            {"id": item["id"], "label": item["label"], "layers": list(item["layers"])}
            for item in LAYER_CATEGORIES
        ],
        "legend_order": [
            layer_id
            for layer_id, _ in sorted(
                LAYER_METADATA.items(),
                key=lambda item: item[1]["legend_order"],
                reverse=True,
            )
        ],
        "field_labels": PROJECT_FIELD_LABELS,
        "identity_fields": list(IDENTITY_FIELDS),
        "all_detail_fields": [
            field
            for field in PROJECT_FIELD_LABELS
            if field not in {"Page Link", "Docket Link"}
        ],
        "psps_scale": PSPS_SCALE,
        "diesel_pm_scale": DIESEL_PM_SCALE,
    }


def _shell_html() -> str:
    return """
<a class="map-app-skip-link" href="#map-app-control">Skip map</a>
<a class="map-app-skip-link map-app-skip-link--projects"
   href="#map-app-projects-button">Skip to project list</a>
<header class="map-app-header" id="map-app-header">
  <div class="map-app-header__copy">
    <h1 class="map-app-header__title">California Data Center Infrastructure</h1>
  </div>
</header>
<section class="map-app-controls" id="map-app-control"
         aria-label="Map views and layers">
  <div class="map-app-controls__header">
    <span class="map-app-controls__title" id="map-app-view-status"></span>
    <button type="button" class="map-app-icon-button"
            aria-label="Collapse map controls"
            aria-expanded="true" data-map-collapse>−</button>
  </div>
  <div class="map-app-tabs" role="tablist" aria-label="Map control type">
    <button type="button" class="map-app-tabs__tab"
            role="tab" aria-selected="true"
            aria-controls="map-app-guided-panel"
            data-map-tab="guided">Guided views</button>
    <button type="button" class="map-app-tabs__tab"
            role="tab" aria-selected="false"
            aria-controls="map-app-diy-panel"
            data-map-tab="diy">Build your own</button>
  </div>
  <div class="map-app-controls__body">
  <div class="map-app-tab-panel" id="map-app-guided-panel" role="tabpanel"
       aria-label="Guided views">
    <div class="map-app-view-list" id="map-app-view-list"></div>
  </div>
  <div class="map-app-tab-panel" id="map-app-diy-panel" role="tabpanel"
       aria-label="Build your own layers" hidden>
    <div class="map-app-layer-list" id="map-app-layer-list"></div>
  </div>
  <div class="map-app-control-actions">
    <button type="button" class="map-app-button map-app-button--quiet"
            id="map-app-reset-view">Reset view</button>
    <button type="button" class="map-app-button map-app-button--quiet"
            id="map-app-reset-map">Reset map</button>
    <button type="button"
            class="map-app-button map-app-button--quiet map-app-methodology-panel"
            data-methodology-open>Methods &amp; sources</button>
    <button type="button" class="map-app-button map-app-button--primary"
            id="map-app-projects-button">Browse projects</button>
  </div>
  </div>
</section>
<aside class="map-app-legend" id="map-app-legend"
       aria-label="Active map legend">
  <div class="map-app-legend__header">
    <h2 class="map-app-legend__title">Legend</h2>
    <button type="button" class="map-app-icon-button"
            aria-label="Collapse legend" aria-expanded="true"
            data-legend-collapse>−</button>
  </div>
  <div class="map-app-legend__body" id="map-app-legend-body"></div>
</aside>
<aside class="map-app-drawer" id="map-app-drawer" hidden
       aria-labelledby="map-app-drawer-title">
  <div class="map-app-drawer__header">
    <div>
      <div class="map-app-drawer__eyebrow" id="map-app-drawer-eyebrow">Project details</div>
      <h2 class="map-app-drawer__title" id="map-app-drawer-title"></h2>
      <p class="map-app-drawer__meta" id="map-app-drawer-meta"></p>
    </div>
    <button type="button" class="map-app-icon-button"
            id="map-app-drawer-close" aria-label="Close project details">×</button>
  </div>
  <div class="map-app-drawer__body" id="map-app-drawer-body"></div>
</aside>
<nav class="map-app-mobile-bar" aria-label="Map tools">
  <button type="button" class="map-app-button" data-mobile-panel="controls">
    Views
  </button>
  <button type="button" class="map-app-button" data-mobile-panel="legend">
    Legend
  </button>
  <button type="button" class="map-app-button" data-mobile-panel="projects">
    Projects
  </button>
</nav>
<input class="map-app-search__input" id="map-app-project-search"
       type="search" placeholder="Search projects, cities, or status"
       aria-label="Search data centers" hidden>
<div class="map-app-project-list" id="map-app-project-list" hidden></div>
<dialog class="map-app-methodology" id="map-app-methodology">
  <div class="map-app-methodology__header">
    <div>
      <div class="map-app-drawer__eyebrow">Documentation</div>
      <h2>Sources &amp; methods</h2>
    </div>
    <button type="button" class="map-app-icon-button"
            id="map-app-methodology-close" aria-label="Close methodology">×</button>
  </div>
  <p><strong>Projects:</strong> California Energy Commission SPPE dockets and
     project filings.</p>
  <p><strong>Grid:</strong> CAISO transmission planning records and CEC
     transmission and substation layers.</p>
  <p><strong>Community context:</strong> CalEnviroScreen 5.0 diesel PM and
     CPUC-reported 2024–2025 PSPS records.</p>
  <p>Spatial proximity does not establish causation, cost responsibility,
     generator operation, or pollution attribution.</p>
  <p>Layer-specific definitions and data coverage are documented in the active
     legend.</p>
</dialog>
<div class="map-app-toast" id="map-app-toast" role="status" hidden></div>
<svg class="map-app-sr-only" aria-hidden="true" width="0" height="0">
  <defs>
    <pattern id="psps-pattern-1" width="12" height="12"
             patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
      <line x1="0" y1="0" x2="0" y2="12" stroke="#049834"
            stroke-width="1" opacity=".46"/>
    </pattern>
    <pattern id="psps-pattern-2" width="11" height="11"
             patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
      <line x1="0" y1="0" x2="0" y2="11" stroke="#049834"
            stroke-width="1.2" opacity=".52"/>
    </pattern>
    <pattern id="psps-pattern-3" width="9" height="9"
             patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
      <line x1="0" y1="0" x2="0" y2="9" stroke="#049834"
            stroke-width="1.3" opacity=".58"/>
    </pattern>
    <pattern id="psps-pattern-4" width="7" height="7"
             patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
      <line x1="0" y1="0" x2="0" y2="7" stroke="#049834"
            stroke-width="1.5" opacity=".64"/>
    </pattern>
    <pattern id="psps-pattern-5" width="5" height="5"
             patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
      <line x1="0" y1="0" x2="0" y2="5" stroke="#049834"
            stroke-width="1.7" opacity=".72"/>
    </pattern>
    <pattern id="psps-pattern-6" width="4" height="4"
             patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
      <line x1="0" y1="0" x2="0" y2="4" stroke="#0033CC"
            stroke-width="2" opacity=".8"/>
    </pattern>
  </defs>
</svg>
<div class="map-app-sr-only" id="map-app-live"
     aria-live="polite" aria-atomic="true"></div>
"""


def _safe_script_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).replace(
        "<", "\\u003c"
    )


def install_ui(
    map_object: folium.Map,
    *,
    layer_registry: Mapping[str, object],
    projects: pd.DataFrame,
    data_center_markers: Sequence[object],
    lazy_layers: Optional[Mapping[str, Mapping]] = None,
    tpp_summary: Optional[Mapping[str, int]] = None,
) -> None:
    """Embed the premium shell and bind it to concrete Leaflet layer objects."""

    if not UI_CSS_PATH.exists() or not UI_JS_PATH.exists():
        raise FileNotFoundError("Map UI assets are missing")
    validate_design_config(
        available_layers=layer_registry,
        available_project_fields=projects.columns,
    )
    project_records = serialize_projects(
        projects, [marker.get_name() for marker in data_center_markers]
    )
    config = browser_config(tpp_summary)
    for layer_id, lazy_config in (lazy_layers or {}).items():
        if layer_id not in config["layers"]:
            raise ValueError(f"Unknown lazy layer ID: {layer_id}")
        config["layers"][layer_id]["lazy"] = dict(lazy_config)
    references = {
        "map_name": map_object.get_name(),
        "layers": {
            layer_id: layer.get_name()
            for layer_id, layer in layer_registry.items()
        },
        "markers": project_records,
        "config": config,
    }

    css = UI_CSS_PATH.read_text(encoding="utf-8")
    runtime = UI_JS_PATH.read_text(encoding="utf-8")
    layer_refs = ",".join(
        f"{json.dumps(layer_id)}:window[{json.dumps(variable)}]"
        for layer_id, variable in references["layers"].items()
    )
    marker_refs = ",".join(
        (
            "{marker:window["
            + json.dumps(item["marker_name"])
            + "],project:"
            + _safe_script_json(item["project"])
            + "}"
        )
        for item in references["markers"]
    )
    bootstrap = f"""
<script>
{runtime}
window.addEventListener("load", function () {{
  window.MapApp.init({{
    map: window[{json.dumps(references["map_name"])}],
    layers: {{{layer_refs}}},
    markers: [{marker_refs}],
    config: {_safe_script_json(references["config"])}
  }});
}});
</script>
"""
    root = map_object.get_root()
    root.header.add_child(
        folium.Element(
            "<style id=\"map-app-styles\">" + html.escape("", quote=False) + css + "</style>"
        )
    )
    root.html.add_child(folium.Element(_shell_html() + bootstrap))
