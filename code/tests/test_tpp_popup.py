from pathlib import Path
import sys
import unittest

import pandas as pd


CODE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CODE_DIR))

from build_phase_zero_map import _tpp_popup_html  # noqa: E402


class TppPopupTests(unittest.TestCase):
    def test_popup_shows_only_requested_public_metadata(self):
        html = _tpp_popup_html(
            pd.Series(
                {
                    "project_name": "Example upgrade",
                    "kV": 230,
                    "approx_miles": 4.5,
                    "notes": "Reconductor the existing line.",
                    "project_cost": "$10M-$20M",
                    "project_id": "2526-R-99",
                    "driver": "Reliability",
                    "geometry_basis": "schematic endpoint connector",
                }
            )
        )
        for expected in (
            "Transmission project",
            "Example upgrade",
            "kV",
            "230",
            "Approx. miles",
            "4.5",
            "Project description",
            "Reconductor the existing line.",
            "Cost",
            "$10M-$20M",
        ):
            self.assertIn(expected, html)
        for excluded in (
            "2526-R-99",
            "Reliability",
            "Geometry",
            "schematic endpoint connector",
        ):
            self.assertNotIn(excluded, html)

    def test_popup_omits_approximate_miles_when_not_numeric(self):
        html = _tpp_popup_html(
            pd.Series(
                {
                    "project_name": "Example substation",
                    "kV": 115,
                    "approx_miles": "",
                    "notes": "Replace circuit breakers.",
                    "project_cost": "$5M",
                }
            )
        )
        self.assertNotIn("Approx. miles", html)


if __name__ == "__main__":
    unittest.main()
