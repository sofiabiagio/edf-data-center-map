"""Publication-grade design contract for the California data-center map.

This module is intentionally free of Folium and Leaflet objects.  It provides
one JSON-serializable source of truth that both the Python map builder and the
browser UI can consume without duplicating labels, colors, class breaks, layer
relationships, or guided-view behavior.

The module does not load or modify research data.  Its validation guards only
the presentation contract: guided views must reference declared layers and
project fields, mutually exclusive representations cannot appear together,
and the core equity comparison must retain both diesel PM and PSPS.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Iterable, Mapping, Optional, Sequence


# These tokens describe a restrained editorial interface.  Numeric sizes are
# expressed in CSS pixels unless their key explicitly names another unit.
DESIGN_TOKENS = {
    "color": {
        "canvas": "#E2E1DF",
        "surface": "#FFFCFC",
        "surface_subtle": "#F4F1F2",
        "ink": "#303034",
        "ink_muted": "#59595C",
        "ink_faint": "#77777A",
        "border": "#D9D9DB",
        "border_strong": "#A9A9AC",
        "focus": "#0033CC",
        "data_center_fill": "#0033CC",
        "data_center_edge": "#0033CC",
        "data_center_selected": "#A1E214",
        "data_center_halo": "#FFFFFF",
        "tpp": "#049834",
        "tpp_new": "#33CCFF",
        "tpp_new_substation": "#A1E214",
        "transmission": "#59595C",
        "substation": "#59595C",
        "lra": "#0033CC",
        "psps": "#049834",
        "missing_fill": "#D7DCDA",
        "missing_edge": "#929D9A",
    },
    "type": {
        "family": (
            "'IBM Plex Sans', ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "
            "'Segoe UI', sans-serif"
        ),
        "size_xs": 11,
        "size_sm": 12,
        "size_md": 14,
        "size_lg": 16,
        "size_xl": 20,
        "line_height_compact": 1.25,
        "line_height_body": 1.5,
        "weight_regular": 400,
        "weight_medium": 500,
        "weight_semibold": 600,
    },
    "space": {
        "1": 4,
        "2": 8,
        "3": 12,
        "4": 16,
        "5": 20,
        "6": 24,
        "8": 32,
    },
    "radius": {
        "small": 4,
        "medium": 6,
        "large": 8,
        "pill": 999,
    },
    "shadow": {
        "panel": "0 8px 24px rgba(48, 48, 52, 0.10)",
        "raised": "0 3px 12px rgba(48, 48, 52, 0.09)",
    },
    "motion": {
        "fast_ms": 120,
        "standard_ms": 180,
        "slow_ms": 240,
        "easing": "cubic-bezier(0.2, 0.8, 0.2, 1)",
    },
    "size": {
        "minimum_touch_target": 44,
        "data_center_minimum_diameter": 12,
        "data_center_maximum_diameter": 30,
        "desktop_control_width": 336,
        "desktop_drawer_width": 408,
        "mobile_breakpoint": 760,
        "mobile_sheet_max_height_dvh": 58,
    },
    "pane_z_index": {
        "utility": 280,
        "diesel": 300,
        "psps": 320,
        "lra": 360,
        "grid_lines": 450,
        "grid_points": 600,
        "data_centers": 650,
    },
}


PROJECT_FIELD_LABELS = {
    "PROJECT_NAME": "Project",
    "PROJECT_TYPE": "Project type",
    "VERIFICATION_NOTE": "Verification status",
    "DOCKET NO. ": "CEC docket",
    "PROJECT_OWNER": "Project owner",
    "PROJECT_STATUS": "Project status",
    "LEVEL_OF_REVIEW": "CEQA review",
    "EXPECTED_COMPLETION": "Expected completion",
    "BACKUP (MW)": "Backup generation (MW)",
    "CITY": "City",
    "COUNTY": "County",
    "ADDRESS": "Address",
    "TOTAL_GENERATORS": "Total generators",
    "TOTAL_LOAD_SERVING_GENERATORS": "Load-serving generators",
    "BGF FUEL TYPE": "Backup fuel",
    "EXPECTED_GENERATOR_TESTING_YR (hrs)": "Expected testing (hours/year)",
    "QUANTITY_FUEL_USED (bbl/yr)": "Fuel use (barrels/year)",
    "SQUARE FOOTAGE (facility)": "Facility area (square feet)",
    "GRID UPGRADES REQUIRED": "Grid upgrades",
    "DEDICATED_FACILITIES": "Dedicated facilities",
    "GRID_INTERCONNECTION": "Grid interconnection",
    "DELIVERY_UTILITY": "Delivery utility",
    "RETAIL_SERVICE_PROVIDER": "Retail service provider",
    "LEND_POWER?": "Can export / participate",
    "POINT_OF_INTERCONNECTION": "Point of interconnection",
    "map_lra": "Local reliability area",
    "map_distribution_utility": "IOU service territory",
    "map_diesel_pm_percentile": "CES 5.0 diesel PM percentile",
    "map_diesel_pm_top_quintile": "CES diesel PM top quintile",
    "map_psps_frequency": "Reported PSPS frequency, 2024–2025",
    "map_psps_status": "PSPS reporting status",
    "Page Link": "CEC project page",
    "Docket Link": "CEC docket",
}


PROJECT_FIELDS_BY_VIEW = {
    "overview": (
        "PROJECT_NAME",
        "PROJECT_STATUS",
        "CITY",
        "COUNTY",
        "EXPECTED_COMPLETION",
        "BACKUP (MW)",
    ),
    "grid_reliability": (
        "PROJECT_NAME",
        "POINT_OF_INTERCONNECTION",
        "GRID_INTERCONNECTION",
        "DELIVERY_UTILITY",
        "GRID UPGRADES REQUIRED",
        "DEDICATED_FACILITIES",
        "map_lra",
        "RETAIL_SERVICE_PROVIDER",
    ),
    "equity_resilience": (
        "PROJECT_NAME",
        "BACKUP (MW)",
        "TOTAL_GENERATORS",
        "TOTAL_LOAD_SERVING_GENERATORS",
        "BGF FUEL TYPE",
        "EXPECTED_GENERATOR_TESTING_YR (hrs)",
        "QUANTITY_FUEL_USED (bbl/yr)",
        "map_diesel_pm_percentile",
        "map_diesel_pm_top_quintile",
        "map_psps_frequency",
        "map_psps_status",
    ),
    "utility_upgrade_evidence": (
        "PROJECT_NAME",
        "map_distribution_utility",
        "RETAIL_SERVICE_PROVIDER",
        "DEDICATED_FACILITIES",
        "GRID UPGRADES REQUIRED",
        "POINT_OF_INTERCONNECTION",
        "GRID_INTERCONNECTION",
        "DELIVERY_UTILITY",
    ),
}


# ``exclusive_family`` identifies alternative renderings of one underlying
# measure.  A missing family means the layer may coexist with every other
# layer.  PSPS deliberately has no exclusive family, so it can be compared
# directly with either diesel representation.
LAYER_METADATA = {
    "data_centers": {
        "label": "CEC SPPE data centers",
        "category": "projects",
        "role": "primary",
        "always_available": True,
        "legend_order": 90,
    },
    "tpp_upgrades": {
        "label": "CAISO transmission plan upgrades",
        "category": "grid_infrastructure",
        "role": "primary",
        "legend_order": 70,
    },
    "transmission_high": {
        "label": "Existing transmission — 230 kV and above",
        "category": "grid_infrastructure",
        "role": "context",
        "semantic_min_zoom": 0,
        "legend_order": 50,
    },
    "transmission_medium": {
        "label": "Existing transmission — 115–229 kV",
        "category": "grid_infrastructure",
        "role": "context",
        "semantic_min_zoom": 8,
        "legend_order": 49,
    },
    "transmission_low": {
        "label": "Existing transmission — below 115 kV",
        "category": "grid_infrastructure",
        "role": "context",
        "semantic_min_zoom": 10,
        "legend_order": 48,
    },
    "substations": {
        "label": "Existing substations",
        "category": "grid_infrastructure",
        "role": "context",
        "semantic_min_zoom": 10,
        "legend_order": 45,
    },
    "lra": {
        "label": "Local Reliability Areas",
        "category": "reliability_jurisdiction",
        "role": "boundary",
        "legend_order": 65,
    },
    "iou_territories": {
        "label": "IOU service territories",
        "category": "reliability_jurisdiction",
        "role": "surface",
        "legend_order": 20,
    },
    "diesel_percentile": {
        "label": "Diesel PM percentile",
        "category": "environment_outage",
        "role": "surface",
        "exclusive_family": "diesel_pm_representation",
        "legend_order": 10,
    },
    "diesel_top_quintile": {
        "label": "Diesel PM top quintile",
        "category": "environment_outage",
        "role": "surface",
        "exclusive_family": "diesel_pm_representation",
        "legend_order": 10,
    },
    "psps_frequency": {
        "label": "Reported PSPS frequency, 2024–2025",
        "category": "environment_outage",
        "role": "pattern",
        "legend_order": 15,
    },
}


GUIDED_VIEWS = {
    "overview": {
        "label": "Overview",
        "question": (
            "Locate proposed facilities and see where planned transmission "
            "investment overlaps."
        ),
        "layers": ("data_centers", "tpp_upgrades"),
        "limitations": (
            "Locations and upgrade geometries reflect the cited project records; "
            "schematic lines are not surveyed routes."
        ),
    },
    "grid_reliability": {
        "label": "Grid & reliability",
        "question": (
            "Compare project clusters with local reliability areas, the "
            "high-voltage network, and CAISO upgrades."
        ),
        "layers": (
            "data_centers",
            "tpp_upgrades",
            "lra",
            "transmission_high",
            "transmission_medium",
            "transmission_low",
            "substations",
        ),
        "limitations": (
            "Proximity does not establish causation, cost responsibility, or "
            "that a transmission project was approved for a data center."
        ),
    },
    "equity_resilience": {
        "label": "Equity & resilience",
        "question": (
            "Find where backup generation coincides with diesel burden and "
            "repeated reported PSPS impacts."
        ),
        "layers": (
            "data_centers",
            "diesel_percentile",
            "psps_frequency",
        ),
        "limitations": (
            "The layers show existing burden and reported PSPS exposure; they "
            "do not prove that a data center operated backup generators during "
            "an outage or caused local pollution."
        ),
    },
    "utility_upgrade_evidence": {
        "label": "Utility & upgrade evidence",
        "question": (
            "Identify the serving utility and inspect evidence of dedicated "
            "facilities or broader grid upgrades."
        ),
        "layers": (
            "data_centers",
            "iou_territories",
            "tpp_upgrades",
        ),
        "limitations": (
            "CEC service-territory boundaries are approximate. Project records "
            "may identify facilities or upgrades without resolving ultimate "
            "cost allocation."
        ),
    },
}


PSPS_SCALE = {
    "field": "sum_monthly_max_customer_events",
    "short_label": "Reported PSPS frequency, 2024–2025",
    "period": "2024–2025",
    "observed_minimum": 1,
    "observed_maximum": 15,
    "method": (
        "For each tract and month, this measure takes the largest number of "
        "PSPS events affecting any one reported customer account, then sums "
        "those monthly values across 2024–2025."
    ),
    "limitations": (
        "This is not a count of distinct regional outages, not the history of "
        "one identified customer, and not proof that a data center operated "
        "backup generators."
    ),
    "missing_label": "No reported impact record / coverage not established",
    "missing_copy": (
        "No reported-impact record is not treated as zero because the source "
        "does not distinguish a covered tract with no impacts from an area "
        "outside the submitting utilities' reported coverage."
    ),
    "classes": (
        {"minimum": 1, "maximum": 1, "label": "1", "pattern": "psps-1"},
        {"minimum": 2, "maximum": 2, "label": "2", "pattern": "psps-2"},
        {"minimum": 3, "maximum": 4, "label": "3–4", "pattern": "psps-3"},
        {"minimum": 5, "maximum": 7, "label": "5–7", "pattern": "psps-4"},
        {"minimum": 8, "maximum": 11, "label": "8–11", "pattern": "psps-5"},
        {"minimum": 12, "maximum": 15, "label": "12–15", "pattern": "psps-6"},
    ),
}


DIESEL_PM_SCALE = {
    "field": "diesel_pm_percentile",
    "short_label": "CalEnviroScreen 5.0 diesel PM percentile",
    "range": (0, 100),
    "top_quintile_threshold": 80,
    "unit": "percentile",
    "interpretation": (
        "The indicator estimates diesel PM emissions from on-road and non-road "
        "sources within and near populated blocks. It is not an ambient "
        "concentration measurement and does not include a proposed data "
        "center's future backup-generator emissions."
    ),
    "missing_label": "No diesel PM value",
    "classes": (
        {"minimum": 0, "maximum": 20, "label": "0–<20", "color": "#F2F0F7"},
        {"minimum": 20, "maximum": 40, "label": "20–<40", "color": "#DADAEB"},
        {"minimum": 40, "maximum": 60, "label": "40–<60", "color": "#BCBDDC"},
        {"minimum": 60, "maximum": 80, "label": "60–<80", "color": "#9E9AC8"},
        {"minimum": 80, "maximum": 90, "label": "80–<90", "color": "#756BB1"},
        {"minimum": 90, "maximum": 100, "label": "90–100", "color": "#54278F"},
    ),
}


def _validate_contiguous_classes(
    classes: Sequence[Mapping[str, object]],
    *,
    minimum: float,
    maximum: float,
    scale_name: str,
    discrete_integer: bool = False,
) -> None:
    """Raise when class definitions overlap, leave gaps, or miss endpoints."""

    if not classes:
        raise ValueError(f"{scale_name} must declare at least one class")
    if classes[0]["minimum"] != minimum or classes[-1]["maximum"] != maximum:
        raise ValueError(
            f"{scale_name} classes must span exactly {minimum}–{maximum}"
        )
    for index, item in enumerate(classes):
        if item["minimum"] > item["maximum"]:
            raise ValueError(f"{scale_name} class {index} has reversed bounds")
        if not str(item.get("label", "")).strip():
            raise ValueError(f"{scale_name} class {index} has no label")
        expected_minimum = (
            classes[index - 1]["maximum"] + 1
            if discrete_integer and index
            else classes[index - 1]["maximum"]
            if index
            else item["minimum"]
        )
        if index and item["minimum"] != expected_minimum:
            raise ValueError(
                f"{scale_name} classes are not contiguous at index {index}"
            )


def validate_design_config(
    *,
    available_layers: Optional[Iterable[str]] = None,
    available_project_fields: Optional[Iterable[str]] = None,
) -> None:
    """Validate cross-references and invariants in the design contract.

    Callers may supply the layer IDs and dataframe columns that exist at build
    time.  Omitting them validates against the declarations in this module.
    This makes a renamed source field or an incompletely constructed layer fail
    clearly before a misleading map is written.
    """

    layers = set(
        LAYER_METADATA if available_layers is None else available_layers
    )
    fields = set(
        PROJECT_FIELD_LABELS
        if available_project_fields is None
        else available_project_fields
    )
    declared_layers = set(LAYER_METADATA)

    missing_runtime_layers = declared_layers.difference(layers)
    if missing_runtime_layers:
        raise ValueError(
            "Design layers missing from the map registry: "
            f"{sorted(missing_runtime_layers)}"
        )

    for view_id, view in GUIDED_VIEWS.items():
        referenced_layers = tuple(view["layers"])
        missing_layers = set(referenced_layers).difference(declared_layers)
        if missing_layers:
            raise ValueError(
                f"Guided view {view_id!r} references unknown layers: "
                f"{sorted(missing_layers)}"
            )
        if len(referenced_layers) != len(set(referenced_layers)):
            raise ValueError(
                f"Guided view {view_id!r} contains duplicate layers"
            )

        families = [
            LAYER_METADATA[layer_id].get("exclusive_family")
            for layer_id in referenced_layers
        ]
        families = [family for family in families if family]
        if len(families) != len(set(families)):
            raise ValueError(
                f"Guided view {view_id!r} selects multiple alternatives from "
                "one exclusive layer family"
            )

        referenced_fields = PROJECT_FIELDS_BY_VIEW.get(view_id)
        if referenced_fields is None:
            raise ValueError(
                f"Guided view {view_id!r} has no project-field schema"
            )
        unknown_fields = set(referenced_fields).difference(
            PROJECT_FIELD_LABELS
        )
        if unknown_fields:
            raise ValueError(
                f"Guided view {view_id!r} references unlabeled fields: "
                f"{sorted(unknown_fields)}"
            )
        missing_fields = set(referenced_fields).difference(fields)
        if missing_fields:
            raise ValueError(
                f"Guided view {view_id!r} references unavailable fields: "
                f"{sorted(missing_fields)}"
            )

    orphan_field_schemas = set(PROJECT_FIELDS_BY_VIEW).difference(GUIDED_VIEWS)
    if orphan_field_schemas:
        raise ValueError(
            "Project-field schemas have no guided view: "
            f"{sorted(orphan_field_schemas)}"
        )

    equity_layers = set(GUIDED_VIEWS["equity_resilience"]["layers"])
    if not {"diesel_percentile", "psps_frequency"}.issubset(equity_layers):
        raise ValueError(
            "The equity view must allow diesel PM and PSPS to coexist"
        )
    if LAYER_METADATA["psps_frequency"].get("exclusive_family"):
        raise ValueError(
            "PSPS must not belong to the diesel representation family"
        )
    diesel_family = {
        layer_id
        for layer_id, metadata in LAYER_METADATA.items()
        if metadata.get("exclusive_family") == "diesel_pm_representation"
    }
    if diesel_family != {"diesel_percentile", "diesel_top_quintile"}:
        raise ValueError(
            "The diesel representation family must contain exactly its "
            "percentile and top-quintile alternatives"
        )

    _validate_contiguous_classes(
        PSPS_SCALE["classes"],
        minimum=PSPS_SCALE["observed_minimum"],
        maximum=PSPS_SCALE["observed_maximum"],
        scale_name="PSPS",
        discrete_integer=True,
    )
    _validate_contiguous_classes(
        DIESEL_PM_SCALE["classes"],
        minimum=DIESEL_PM_SCALE["range"][0],
        maximum=DIESEL_PM_SCALE["range"][1],
        scale_name="Diesel PM",
    )


def browser_design_config() -> dict:
    """Return a defensive, JSON-ready copy for the browser runtime."""

    validate_design_config()
    return deepcopy(
        {
            "tokens": DESIGN_TOKENS,
            "layers": LAYER_METADATA,
            "views": GUIDED_VIEWS,
            "projectFieldsByView": PROJECT_FIELDS_BY_VIEW,
            "projectFieldLabels": PROJECT_FIELD_LABELS,
            "pspsScale": PSPS_SCALE,
            "dieselPmScale": DIESEL_PM_SCALE,
        }
    )


validate_design_config()
