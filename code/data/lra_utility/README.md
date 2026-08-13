# LRA and electric service-area cache

This directory is managed by `code/lra_utility_layers.py`.

Run:

```bash
./.venv/bin/python code/lra_utility_layers.py --refresh
```

The command downloads official ArcGIS polygon services, repairs invalid source
polygons without simplifying them, and writes:

- `lra_utility_layers.gpkg`
  - `local_reliability_areas`
  - `electric_service_areas`
- `source_manifest.json`
- `validation_report.json`

Sources:

- CPUC, Local Reliability Areas:
  `https://gis.cpuc.ca.gov/server/rest/services/Hosted/LocalReliabilityAreas/FeatureServer/0`
- CEC, Electric Load Serving Entities (IOU & POU):
  `https://services3.arcgis.com/bWPjFyq029ChCGur/arcgis/rest/services/ElectricLoadServingEntities_IOU_POU/FeatureServer/0`
- CEC, Electric Load Serving Entities (Other):
  `https://services3.arcgis.com/bWPjFyq029ChCGur/arcgis/rest/services/ElectricLoadServingEntities_Other/FeatureServer/0`

Important: CEC describes the utility boundaries as approximate. CCA polygons
overlap distribution utilities; they are retained in the all-LSE cache but are
excluded by the module's default distribution-territory loader.
