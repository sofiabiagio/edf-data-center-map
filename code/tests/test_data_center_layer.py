from pathlib import Path
import sys
import unittest

import pandas as pd


CODE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CODE_DIR))

from build_phase_zero_map import (  # noqa: E402
    DATA_CENTER_PATH,
    _data_center_popup,
    enrich_data_centers,
    load_mappable_data_centers,
)
from diesel_pm_layer import load_diesel_pm_data  # noqa: E402
from lra_utility_layers import load_lra, load_utility_territories  # noqa: E402
from psps_frequency_layer import load_psps_frequency_layer  # noqa: E402


class DataCenterLayerTests(unittest.TestCase):
    def test_only_documented_project_rows_with_valid_coordinates_are_mapped(self):
        projects, total = load_mappable_data_centers()
        source = pd.read_csv(DATA_CENTER_PATH).assign(
            PROJECT_TYPE="CEC SPPE data center"
        )
        documented = source[
            source["DOCKET NO. "].astype(str).str.fullmatch(
                r"\d{2}-SPPE-\d{2}",
                na=False,
            )
        ].copy()
        latitude = pd.to_numeric(
            documented["LAT"]
            .astype("string")
            .str.strip()
            .str.replace(r"[,\s]+$", "", regex=True),
            errors="coerce",
        )
        longitude = pd.to_numeric(
            documented["LONG"]
            .astype("string")
            .str.strip()
            .str.replace(r"[,\s]+$", "", regex=True),
            errors="coerce",
        )
        expected_mappable = latitude.between(32, 43) & longitude.between(
            -125,
            -113,
        )

        self.assertEqual(total, len(documented))
        self.assertEqual(len(projects), int(expected_mappable.sum()))
        self.assertTrue(projects["LAT"].between(32, 43).all())
        self.assertTrue(projects["LONG"].between(-125, -113).all())
        self.assertFalse(
            projects["PROJECT_NAME"].str.startswith("Name of project").any()
        )
        self.assertEqual(set(projects["PROJECT_TYPE"]), {"CEC SPPE data center"})

    def test_popup_exposes_collected_fields_and_source_links(self):
        projects, _ = load_mappable_data_centers()
        popup = _data_center_popup(projects.iloc[0])
        self.assertIn("Backup generation (MW)", popup)
        self.assertIn("Grid upgrades", popup)
        self.assertIn("Dedicated facilities", popup)
        self.assertIn("Grid interconnection", popup)
        self.assertIn("Delivery utility", popup)
        self.assertIn("Retail service provider", popup)
        self.assertIn("CEC project page", popup)
        self.assertIn("Docket", popup)

    def test_context_values_are_joined_without_treating_missing_psps_as_zero(self):
        projects, _ = load_mappable_data_centers()
        enriched = enrich_data_centers(
            projects,
            lra=load_lra(),
            utilities=load_utility_territories(),
            diesel_pm=load_diesel_pm_data(),
            psps_frequency=load_psps_frequency_layer(),
        )
        self.assertTrue(enriched["map_distribution_utility"].notna().all())
        self.assertTrue(enriched["map_diesel_pm_percentile"].notna().all())
        self.assertTrue(
            enriched["map_psps_status"]
            .str.contains("reported|not treated as zero", case=False)
            .all()
        )


if __name__ == "__main__":
    unittest.main()
