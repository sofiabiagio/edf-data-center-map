import json
from pathlib import Path
import sys
import unittest


CODE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CODE_DIR))

from map_design import (  # noqa: E402
    DESIGN_TOKENS,
    DIESEL_PM_SCALE,
    GUIDED_VIEWS,
    LAYER_METADATA,
    PROJECT_FIELD_LABELS,
    PROJECT_FIELDS_BY_VIEW,
    PSPS_SCALE,
    browser_design_config,
    validate_design_config,
)


class MapDesignContractTests(unittest.TestCase):
    def test_design_contract_validates(self):
        validate_design_config()

    def test_guided_views_are_the_approved_four_views(self):
        self.assertEqual(
            tuple(GUIDED_VIEWS),
            (
                "overview",
                "grid_reliability",
                "equity_resilience",
                "utility_upgrade_evidence",
            ),
        )
        self.assertEqual(
            {view["label"] for view in GUIDED_VIEWS.values()},
            {
                "Overview",
                "Grid & reliability",
                "Equity & resilience",
                "Utility & upgrade evidence",
            },
        )
        for view_id, view in GUIDED_VIEWS.items():
            with self.subTest(view=view_id):
                self.assertTrue(view["question"].strip())
                self.assertTrue(view["limitations"].strip())
                self.assertIn("data_centers", view["layers"])
                self.assertIn(view_id, PROJECT_FIELDS_BY_VIEW)

    def test_guided_view_layer_matrix_matches_the_product_contract(self):
        self.assertEqual(
            GUIDED_VIEWS["overview"]["layers"],
            ("data_centers", "tpp_upgrades"),
        )
        self.assertEqual(
            set(GUIDED_VIEWS["equity_resilience"]["layers"]),
            {
                "data_centers",
                "diesel_percentile",
                "psps_frequency",
            },
        )
        self.assertEqual(
            set(GUIDED_VIEWS["utility_upgrade_evidence"]["layers"]),
            {
                "data_centers",
                "iou_territories",
                "tpp_upgrades",
            },
        )
        self.assertEqual(
            set(GUIDED_VIEWS["grid_reliability"]["layers"]),
            {
                "data_centers",
                "tpp_upgrades",
                "lra",
                "transmission_high",
                "transmission_medium",
                "transmission_low",
                "substations",
            },
        )

    def test_no_guided_view_selects_both_diesel_representations(self):
        alternatives = {"diesel_percentile", "diesel_top_quintile"}
        for view_id, view in GUIDED_VIEWS.items():
            with self.subTest(view=view_id):
                self.assertLessEqual(
                    len(alternatives.intersection(view["layers"])),
                    1,
                )
        self.assertNotIn(
            "exclusive_family",
            LAYER_METADATA["psps_frequency"],
        )

    def test_semantic_zoom_and_visual_stack_preserve_map_hierarchy(self):
        self.assertEqual(
            LAYER_METADATA["transmission_high"]["semantic_min_zoom"],
            0,
        )
        self.assertEqual(
            LAYER_METADATA["transmission_medium"]["semantic_min_zoom"],
            8,
        )
        self.assertEqual(
            LAYER_METADATA["transmission_low"]["semantic_min_zoom"],
            10,
        )
        self.assertEqual(
            LAYER_METADATA["substations"]["semantic_min_zoom"],
            10,
        )
        panes = DESIGN_TOKENS["pane_z_index"]
        self.assertLess(panes["diesel"], panes["psps"])
        self.assertLess(panes["psps"], panes["lra"])
        self.assertLess(panes["lra"], panes["grid_lines"])
        self.assertLess(panes["grid_lines"], panes["grid_points"])
        self.assertLess(panes["grid_points"], panes["data_centers"])

    def test_psps_scale_has_exact_published_range_and_classes(self):
        self.assertEqual(
            PSPS_SCALE["short_label"],
            "Reported PSPS frequency, 2024–2025",
        )
        self.assertEqual(PSPS_SCALE["period"], "2024–2025")
        self.assertEqual(
            (
                PSPS_SCALE["observed_minimum"],
                PSPS_SCALE["observed_maximum"],
            ),
            (1, 15),
        )
        self.assertEqual(
            [item["label"] for item in PSPS_SCALE["classes"]],
            ["1", "2", "3–4", "5–7", "8–11", "12–15"],
        )
        self.assertEqual(
            [
                (item["minimum"], item["maximum"])
                for item in PSPS_SCALE["classes"]
            ],
            [(1, 1), (2, 2), (3, 4), (5, 7), (8, 11), (12, 15)],
        )
        self.assertEqual(
            len({item["pattern"] for item in PSPS_SCALE["classes"]}),
            6,
        )

    def test_psps_copy_quantifies_the_measure_without_implying_zero(self):
        self.assertIn("each tract and month", PSPS_SCALE["method"])
        self.assertIn("largest number", PSPS_SCALE["method"])
        self.assertIn("2024–2025", PSPS_SCALE["method"])
        self.assertEqual(
            PSPS_SCALE["missing_label"],
            "No reported impact record / coverage not established",
        )
        self.assertIn("not treated as zero", PSPS_SCALE["missing_copy"])
        self.assertIn(
            "not a count of distinct regional outages",
            PSPS_SCALE["limitations"],
        )
        self.assertIn(
            "not proof that a data center operated backup generators",
            PSPS_SCALE["limitations"],
        )

    def test_diesel_scale_is_distinct_and_marks_the_top_quintile(self):
        self.assertEqual(DIESEL_PM_SCALE["range"], (0, 100))
        self.assertEqual(DIESEL_PM_SCALE["top_quintile_threshold"], 80)
        self.assertEqual(
            [item["minimum"] for item in DIESEL_PM_SCALE["classes"]],
            [0, 20, 40, 60, 80, 90],
        )
        self.assertEqual(
            [item["maximum"] for item in DIESEL_PM_SCALE["classes"]],
            [20, 40, 60, 80, 90, 100],
        )
        self.assertEqual(
            len({item["color"] for item in DIESEL_PM_SCALE["classes"]}),
            6,
        )
        self.assertNotEqual(
            DESIGN_TOKENS["color"]["psps"],
            DIESEL_PM_SCALE["classes"][-1]["color"],
        )
        self.assertIn(
            "not an ambient concentration",
            DIESEL_PM_SCALE["interpretation"],
        )
        self.assertIn("No diesel PM value", DIESEL_PM_SCALE["missing_label"])

    def test_project_field_schemas_are_labeled_and_view_specific(self):
        self.assertEqual(set(PROJECT_FIELDS_BY_VIEW), set(GUIDED_VIEWS))
        for view_id, fields in PROJECT_FIELDS_BY_VIEW.items():
            with self.subTest(view=view_id):
                self.assertEqual(len(fields), len(set(fields)))
                self.assertTrue(set(fields).issubset(PROJECT_FIELD_LABELS))
                self.assertEqual(fields[0], "PROJECT_NAME")

        self.assertTrue(
            {
                "map_diesel_pm_percentile",
                "map_psps_frequency",
                "map_psps_status",
            }.issubset(PROJECT_FIELDS_BY_VIEW["equity_resilience"])
        )
        self.assertTrue(
            {
                "POINT_OF_INTERCONNECTION",
                "GRID UPGRADES REQUIRED",
                "DEDICATED_FACILITIES",
                "map_lra",
            }.issubset(PROJECT_FIELDS_BY_VIEW["grid_reliability"])
        )
        self.assertTrue(
            {
                "map_distribution_utility",
                "RETAIL_SERVICE_PROVIDER",
                "GRID UPGRADES REQUIRED",
                "DEDICATED_FACILITIES",
            }.issubset(PROJECT_FIELDS_BY_VIEW["utility_upgrade_evidence"])
        )

    def test_accessibility_and_motion_tokens_meet_the_experience_contract(self):
        sizes = DESIGN_TOKENS["size"]
        self.assertGreaterEqual(sizes["minimum_touch_target"], 44)
        self.assertGreaterEqual(sizes["data_center_minimum_diameter"], 12)
        self.assertGreater(
            sizes["data_center_maximum_diameter"],
            sizes["data_center_minimum_diameter"],
        )
        self.assertLessEqual(sizes["mobile_breakpoint"], 768)
        self.assertLessEqual(DESIGN_TOKENS["motion"]["standard_ms"], 200)
        self.assertTrue(DESIGN_TOKENS["color"]["focus"].startswith("#"))

    def test_browser_config_is_json_serializable_and_defensive(self):
        first = browser_design_config()
        json.dumps(first)
        first["views"]["overview"]["layers"] = ("corrupted",)
        first["tokens"]["color"]["ink"] = "corrupted"

        second = browser_design_config()
        self.assertEqual(
            second["views"]["overview"]["layers"],
            ("data_centers", "tpp_upgrades"),
        )
        self.assertEqual(second["tokens"]["color"]["ink"], "#303034")

    def test_validator_rejects_missing_runtime_layer(self):
        available_layers = set(LAYER_METADATA).difference({"lra"})
        with self.assertRaisesRegex(
            ValueError,
            "Design layers missing from the map registry.*lra",
        ):
            validate_design_config(available_layers=available_layers)

    def test_validator_rejects_missing_runtime_project_field(self):
        available_fields = set(PROJECT_FIELD_LABELS).difference(
            {"POINT_OF_INTERCONNECTION"}
        )
        with self.assertRaisesRegex(
            ValueError,
            "references unavailable fields.*POINT_OF_INTERCONNECTION",
        ):
            validate_design_config(
                available_project_fields=available_fields,
            )


if __name__ == "__main__":
    unittest.main()
