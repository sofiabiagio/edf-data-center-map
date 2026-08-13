from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

import geopandas as gpd
from shapely.geometry import Point


CODE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CODE_DIR))

from tpp_geometry import (  # noqa: E402
    EndpointResolutionError,
    arcgis_to_gdf,
    geometry_class_for,
    load_and_validate_tpp_inventory,
    resolve_endpoint,
)


class TppGeometryTests(unittest.TestCase):
    def test_official_inventory_has_complete_component_coverage(self):
        manifest, components = load_and_validate_tpp_inventory(
            CODE_DIR / "tpp_projects.csv",
            CODE_DIR / "tpp_upgrades.csv",
        )
        self.assertEqual(len(manifest), 38)
        self.assertEqual(manifest["project_id"].nunique(), 38)
        self.assertEqual(components["project_id"].nunique(), 38)
        self.assertEqual(len(components), 42)
        for project_id in (
            "2425-R-02",
            "1314-R-17",
            "2425-R-25",
            "1819-E-01",
            "2324-R-20",
        ):
            self.assertIn(project_id, set(components["project_id"]))
        imperial = components.loc[components["project_id"].eq("2324-R-20")].iloc[0]
        self.assertEqual(imperial["bucket"], "substation")
        ames_distribution = components.loc[
            components["project_id"].eq("2425-R-02")
        ].iloc[0]
        self.assertEqual(ames_distribution["bucket"], "substation")

    def test_geometry_classes_distinguish_approximate_from_schematic(self):
        self.assertEqual(
            geometry_class_for(
                "existing_line",
                "approximate mapped line segment near Clairemont",
            ),
            "line_existing_approximate",
        )
        self.assertEqual(
            geometry_class_for(
                "existing_line",
                "schematic existing-line endpoint connector: A – B",
            ),
            "line_existing_schematic",
        )

    def test_endpoint_resolution_is_exact_or_explicit_alias_only(self):
        substations = gpd.GeoDataFrame(
            {
                "Name": ["Los Esteros", "Other"],
                "Owner": ["PG&E", "PG&E"],
                "Max_Voltag": [230, 115],
                "COUNTY": ["Santa Clara County", "Elsewhere"],
                "CITY": ["San Jose", "Other"],
            },
            geometry=[Point(-121.8, 37.4), Point(-120, 36)],
            crs=4326,
        )
        point, basis = resolve_endpoint("Los-Esteros", substations)
        self.assertEqual(point, substations.geometry.iloc[0])
        self.assertEqual(basis, "Los-Esteros → Los Esteros")
        with self.assertRaises(EndpointResolutionError):
            resolve_endpoint("Los Estero", substations)

    @patch("tpp_geometry.requests.get")
    def test_arcgis_download_is_paginated_ordered_and_count_checked(self, get):
        def response(payload):
            mock = Mock()
            mock.raise_for_status.return_value = None
            mock.json.return_value = payload
            return mock

        get.side_effect = [
            response({"layers": [{"id": 7}]}),
            response(
                {
                    "objectIdField": "OBJECTID",
                    "fields": [
                        {
                            "name": "OBJECTID",
                            "type": "esriFieldTypeOID",
                        }
                    ],
                }
            ),
            response({"count": 3}),
            response(
                {
                    "features": [
                        {
                            "type": "Feature",
                            "properties": {"OBJECTID": 1},
                            "geometry": {
                                "type": "Point",
                                "coordinates": [-121, 37],
                            },
                        },
                        {
                            "type": "Feature",
                            "properties": {"OBJECTID": 2},
                            "geometry": {
                                "type": "Point",
                                "coordinates": [-120, 36],
                            },
                        },
                    ]
                }
            ),
            response(
                {
                    "features": [
                        {
                            "type": "Feature",
                            "properties": {"OBJECTID": 3},
                            "geometry": {
                                "type": "Point",
                                "coordinates": [-119, 35],
                            },
                        }
                    ]
                }
            ),
        ]
        frame = arcgis_to_gdf("https://example.test/FeatureServer", page_size=2)
        self.assertEqual(len(frame), 3)
        query_calls = [
            call
            for call in get.call_args_list
            if call.args[0].endswith("/query")
            and "resultOffset" in call.kwargs.get("params", {})
        ]
        self.assertEqual(
            [call.kwargs["params"]["resultOffset"] for call in query_calls],
            [0, 2],
        )
        self.assertTrue(
            all(
                call.kwargs["params"]["orderByFields"] == "OBJECTID"
                for call in query_calls
            )
        )


if __name__ == "__main__":
    unittest.main()
