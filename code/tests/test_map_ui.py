from pathlib import Path
import sys
import unittest


CODE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CODE_DIR))

from map_ui import browser_config  # noqa: E402


class MapUiContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = browser_config()
        cls.html = (CODE_DIR.parent / "dist" / "index.html").read_text(encoding="utf-8")

    def test_generated_map_has_publication_metadata_and_scalable_viewport(self):
        self.assertIn('<html lang="en">', self.html)
        self.assertIn(
            "<title>California Data Centers, Grid & Community Context</title>",
            self.html,
        )
        self.assertIn(
            'content="width=device-width, initial-scale=1.0"',
            self.html,
        )
        self.assertNotIn("user-scalable=no", self.html)
        self.assertNotIn("maximum-scale=1.0", self.html)

    def test_generated_map_contains_premium_shell_and_accessibility_routes(self):
        for expected in (
            'id="map-app-control"',
            'id="map-app-legend"',
            'id="map-app-drawer"',
            'id="map-app-project-list"',
            'id="map-app-live"',
            'href="#map-app-control"',
            'href="#map-app-projects-button"',
            'role="tablist"',
            'aria-label="Map tools"',
            "Methods &amp; sources",
        ):
            self.assertIn(expected, self.html)

    def test_discrete_actions_support_browser_history_restoration(self):
        self.assertIn('history[push ? "pushState" : "replaceState"]', self.html)
        self.assertIn('window.addEventListener("popstate"', self.html)
        self.assertIn("restoreUrlState();", self.html)

    def test_removed_layer_ids_in_shared_urls_are_ignored(self):
        self.assertIn(
            'layerParam.split(",").filter((id) => config.layers[id])',
            self.html,
        )

    def test_generated_map_has_all_guided_views_and_shared_psps_patterns(self):
        for view in self.config["views"].values():
            self.assertIn(view["label"], self.html)
            self.assertIn(view["question"], self.html)
        for index in range(1, 7):
            self.assertIn(f'id="psps-pattern-{index}"', self.html)
        self.assertIn("data/web/psps_frequency.geojson", self.html)
        self.assertIn("url(#psps-pattern-${index})", self.html)
        self.assertIn("Observed mapped range: 1–15", self.html)
        self.assertIn(
            "No reported impact record / coverage not established",
            self.html,
        )

    def test_legends_explain_geometry_scale_and_missing_data(self):
        tpp_items = self.config["layers"]["tpp_upgrades"]["legend"]["items"]
        self.assertEqual(
            [item.get("line_case") for item in tpp_items[:2]],
            [
                "existing-line-work",
                "new-line-work",
            ],
        )
        self.assertEqual(
            {
                self.config["layers"][layer_id]["legend"]["group"]
                for layer_id in (
                    "transmission_high",
                    "transmission_medium",
                    "transmission_low",
                )
            },
            {"existing_transmission"},
        )
        self.assertIn("Definition & caveats", self.html)
        self.assertIn("map-app-legend__item--missing", self.html)
        self.assertIn("Cluster · number is project count", self.html)
        self.assertNotIn(
            "missing",
            self.config["layers"]["diesel_percentile"]["legend"],
        )
        self.assertNotIn(
            "missing",
            self.config["layers"]["diesel_top_quintile"]["legend"],
        )
        self.assertIn(
            "missing",
            self.config["layers"]["psps_frequency"]["legend"],
        )

    def test_edf_palette_is_applied_to_map_layers(self):
        tokens = self.config["tokens"]
        self.assertEqual(tokens["data_center"], "#0033CC")
        self.assertEqual(
            self.config["layers"]["tpp_upgrades"]["legend"]["items"][0][
                "color"
            ],
            "#049834",
        )
        self.assertEqual(
            self.config["layers"]["tpp_upgrades"]["legend"]["items"][1][
                "color"
            ],
            "#33CCFF",
        )
        self.assertEqual(
            self.config["layers"]["tpp_upgrades"]["legend"]["items"][3][
                "color"
            ],
            "#A1E214",
        )
        self.assertIn("#A1E214", self.html)
        self.assertIn("#54278F", self.html)
        self.assertIn("#049834", self.html)

    def test_current_artifact_includes_all_mappable_projects(self):
        self.assertEqual(
            self.html.count('"aria-label","Open details for'),
            0,
            "Accessibility labels are installed at runtime, not duplicated in data",
        )
        self.assertEqual(self.html.count("marker:window["), 14)
        self.assertNotIn("Non-SPPE", self.html)
        self.assertNotIn("verification in progress", self.html)

    def test_legacy_control_and_legend_are_not_shipped(self):
        self.assertNotIn("GroupedLayerControl", self.html)
        self.assertNotIn('id="legend" style="position:fixed', self.html)
        self.assertNotIn("PSPS frequency proxy (2024", self.html)

    def test_heavy_layers_are_lazy_loaded_and_initial_shell_is_small(self):
        for asset in (
            "substations.geojson",
            "transmission_high.geojson",
            "transmission_medium.geojson",
            "transmission_low.geojson",
            "diesel_percentile.geojson",
            "diesel_top_quintile.geojson",
            "psps_frequency.geojson",
        ):
            self.assertIn(f"data/web/{asset}", self.html)
            self.assertTrue((CODE_DIR.parent / "dist" / "data" / "web" / asset).exists())
            script_asset = Path(asset).with_suffix(".js")
            self.assertIn(f"data/web/{script_asset}", self.html)
            self.assertTrue(
                (CODE_DIR.parent / "dist" / "data" / "web" / script_asset).exists()
            )
        self.assertLess(len(self.html.encode("utf-8")), 1_300_000)

    def test_lazy_layers_support_direct_file_opening(self):
        self.assertIn(
            'window.location.protocol === "file:"',
            self.html,
        )
        self.assertIn("loadLocalLayerScript", self.html)
        self.assertIn("window.__MAP_APP_LAYER_DATA__", self.html)

    def test_tpp_popup_uses_readable_text_on_light_surface(self):
        self.assertIn(".map-app-tpp-card {", self.html)
        self.assertIn("color: #303034;", self.html)
        self.assertIn(".map-app-tpp-card__title", self.html)
        self.assertIn("color: #16161a;", self.html)


if __name__ == "__main__":
    unittest.main()
