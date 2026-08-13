from pathlib import Path
import sys
import unittest

import folium


CODE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CODE_DIR))

from psps_frequency_layer import (  # noqa: E402
    METRIC_FIELD,
    add_psps_frequency_layer,
    load_california_tracts,
    load_psps_frequency_layer,
    load_psps_records,
    validate_psps_layer,
)


class PspsFrequencyLayerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tracts = load_california_tracts()
        cls.records = load_psps_records()
        cls.layer = load_psps_frequency_layer()

    def test_source_coverage_and_geography_normalization(self):
        counts = self.records["geography_status"].value_counts().to_dict()
        self.assertEqual(len(self.records), 2_971)
        self.assertEqual(counts["utility_geoid_matches_2010_geography"], 2_926)
        self.assertEqual(
            counts[
                "newer_utility_geoid_normalized_to_2010_by_submitted_geometry"
            ],
            39,
        )
        self.assertEqual(
            counts["2010_geoid_assigned_from_submitted_geometry"], 2
        )
        self.assertEqual(
            counts["unlocatable_null_geometry_and_tract"], 4
        )

    def test_published_metric_and_geometry(self):
        summary = validate_psps_layer(self.layer, self.records)
        self.assertEqual(summary["reported_impact_tract_units"], 1_546)
        self.assertEqual(summary["metric_min"], 1)
        self.assertEqual(summary["metric_max"], 15)
        self.assertEqual(summary["metric_sum"], 3_838)
        self.assertEqual(summary["tract_vintage"], "2010")
        self.assertEqual(summary["unlocatable_source_records"], 4)
        self.assertEqual(summary["unlocatable_customer_accounts"], 23)

        canonical = self.tracts.set_index("GEOID").geometry
        published = self.layer.set_index("GEOID").geometry
        self.assertTrue(
            published.geom_equals(canonical.loc[published.index]).all()
        )

    def test_duplicate_source_rows_are_not_summed_within_month(self):
        sdge_january = self.records[
            (self.records["utility"] == "SDG&E")
            & (self.records["report_year"] == 2025)
            & (self.records["YYYYMM"] == "202501")
        ]
        duplicated = sdge_january[
            sdge_january.duplicated(["GEOID", "YYYYMM"], keep=False)
        ]
        self.assertGreater(len(duplicated), 0)
        for geoid, rows in duplicated.groupby("GEOID"):
            self.assertEqual(
                int(rows["MaxEvents"].max()),
                int(
                    self.layer.loc[
                        self.layer["GEOID"] == geoid,
                        "max_monthly_max_customer_events",
                    ].iloc[0]
                ),
            )

    def test_folium_layer_renders_with_method_disclosure(self):
        map_object = folium.Map(location=[37.2, -119.5], zoom_start=5)
        layer = add_psps_frequency_layer(
            map_object,
            layer=self.layer,
            simplify_meters=300,
        )
        rendered = map_object.get_root().render()
        self.assertEqual(
            layer.layer_name,
            "Reported PSPS frequency, 2024–2025",
        )
        self.assertIn(METRIC_FIELD, rendered)
        self.assertIn("2010 Census geography", rendered)


if __name__ == "__main__":
    unittest.main()
