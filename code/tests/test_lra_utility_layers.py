from pathlib import Path
import sys
import unittest

import folium


CODE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CODE_DIR))

from lra_utility_layers import (  # noqa: E402
    add_lra_layer,
    add_utility_layer,
    load_lra,
    load_utility_territories,
    simplify_for_web,
    validate_layers,
)


class LraUtilityLayerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lra = load_lra(current_only=False)
        cls.utilities = load_utility_territories(distribution_only=False)

    def test_cached_official_layer_structure(self):
        summary = validate_layers(self.lra, self.utilities)
        self.assertEqual(summary["lra_features"], 10)
        self.assertEqual(summary["current_lra_features"], 10)
        self.assertEqual(summary["utility_features_all_published_lse"], 85)
        self.assertEqual(summary["utility_features_distribution"], 59)
        self.assertEqual(summary["utility_features_iou"], 6)
        self.assertTrue(summary["crs_is_wgs84"])
        self.assertTrue(summary["all_geometries_nonempty"])
        self.assertTrue(summary["all_geometries_valid"])
        self.assertTrue(summary["all_geometries_polygonal"])

    def test_distribution_default_excludes_overlapping_suppliers(self):
        distribution = load_utility_territories(distribution_only=True)
        self.assertEqual(len(distribution), 59)
        self.assertTrue(
            distribution["territory_role"].eq("distribution_utility").all()
        )
        self.assertFalse(distribution["service_type"].eq("CCA").any())
        self.assertFalse(distribution["service_type"].eq("ADMIN").any())

    def test_web_simplification_preserves_area_and_validity(self):
        for frame in (self.lra, load_utility_territories()):
            simplified = simplify_for_web(frame, tolerance_m=100)
            before = frame.to_crs(3310).geometry.area.sum()
            after = simplified.to_crs(3310).geometry.area.sum()
            self.assertLess(abs(after - before) / before, 0.005)
            self.assertTrue(simplified.geometry.is_valid.all())

    def test_folium_layers_include_source_caveats(self):
        map_object = folium.Map(location=[37.2, -119.5], zoom_start=5)
        add_lra_layer(map_object, frame=self.lra, pane="overlayPane")
        add_utility_layer(
            map_object,
            frame=load_utility_territories(),
            pane="overlayPane",
        )
        rendered = map_object.get_root().render()
        self.assertIn("Current in published source", rendered)
        self.assertIn("Source last edited (UTC)", rendered)
        self.assertIn("Boundary note", rendered)
        self.assertIn("boundaries are approximate", rendered)


if __name__ == "__main__":
    unittest.main()
