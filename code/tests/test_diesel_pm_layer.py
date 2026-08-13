from pathlib import Path
import sys
import unittest

import folium


CODE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CODE_DIR))

from diesel_pm_layer import (  # noqa: E402
    EXPECTED_DIESEL_MISSING,
    EXPECTED_TRACTS,
    load_diesel_pm_data,
    make_diesel_pm_layer,
    validate_diesel_pm_data,
)


class DieselPmLayerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.diesel_tracts = load_diesel_pm_data()

    def test_final_release_schema_and_quality(self):
        summary = validate_diesel_pm_data(self.diesel_tracts)
        self.assertEqual(summary["row_count"], EXPECTED_TRACTS)
        self.assertEqual(summary["unique_tracts"], EXPECTED_TRACTS)
        self.assertEqual(summary["missing_raw"], EXPECTED_DIESEL_MISSING)
        self.assertEqual(summary["missing_percentile"], EXPECTED_DIESEL_MISSING)
        self.assertGreaterEqual(summary["minimum_percentile"], 0)
        self.assertLessEqual(summary["maximum_percentile"], 100)
        self.assertEqual(summary["invalid_geometries"], 0)
        self.assertEqual(self.diesel_tracts.crs.to_epsg(), 4326)
        self.assertTrue(
            self.diesel_tracts["tract_geoid"].str.fullmatch(r"\d{11}").all()
        )

    def test_missing_sentinel_is_normalized(self):
        self.assertFalse(
            (
                self.diesel_tracts["diesel_pm_tons_per_year"].dropna()
                == -999
            ).any()
        )
        self.assertFalse(
            (
                self.diesel_tracts["diesel_pm_percentile"].dropna()
                == -999
            ).any()
        )
        self.assertTrue(
            self.diesel_tracts.loc[
                self.diesel_tracts["diesel_pm_percentile"].isna(),
                "diesel_pm_top_quintile",
            ].isna().all()
        )

    def test_top_quintile_definition(self):
        expected = (
            self.diesel_tracts["diesel_pm_percentile"]
            .ge(80)
            .fillna(False)
            .astype("boolean")
        )
        actual = self.diesel_tracts["diesel_pm_top_quintile"].fillna(False)
        self.assertTrue(actual.equals(expected))
        self.assertEqual(int(actual.sum()), 1_820)

    def test_folium_layers_render(self):
        for mode in ("percentile", "top_quintile"):
            with self.subTest(mode=mode):
                map_object = folium.Map(location=[37.2, -119.5], zoom_start=5)
                layer = make_diesel_pm_layer(
                    self.diesel_tracts,
                    mode=mode,
                    simplify_tolerance=0.002,
                )
                layer.add_to(map_object)
                rendered = map_object.get_root().render()
                self.assertIn("CES 5.0 diesel PM", layer.layer_name)
                self.assertIn("Diesel PM emissions (tons/year)", rendered)
                self.assertIn("diesel_pm_percentile", rendered)


if __name__ == "__main__":
    unittest.main()
