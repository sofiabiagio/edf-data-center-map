# CalEnviroScreen 5.0 diesel PM source cache

This directory contains the authoritative **final** CalEnviroScreen 5.0
release used by `code/diesel_pm_layer.py`. It does not use the earlier draft
CES 5.0 dataset.

## Cached source files

- `calenviroscreen50results_f_070126.shp.zip`
  - Final census-tract shapefile released by California OEHHA in July 2026.
  - Source: https://data.ca.gov/dataset/72b28c84-ceac-4886-9f71-d422470d2223/resource/e3d16016-1828-424f-85a6-f7731033d338/download/calenviroscreen50results_f_070126.shp.zip
  - SHA-256: `00227174d2cb3489f8b7e13d929825274e1cb4c11a3715952762df9e27a991bd`
- `final-calenviroscreen-5.0-data-dictionary.pdf`
  - Official results data dictionary and missing-value guidance.
  - Source: https://data.ca.gov/dataset/72b28c84-ceac-4886-9f71-d422470d2223/resource/31ddb21a-44bb-4cb0-81d8-6e2f80ee359d/download/final-calenviroscreen-5.0-data-dictionary.pdf
  - SHA-256: `1c730d0a9a7e727185039d2850d466ebc76ebcbc0b986e0d5494ca0388fe7eab`

Dataset landing page:
https://lab.data.ca.gov/dataset/calenviroscreen-5-0

Final ArcGIS FeatureServer:
https://services1.arcgis.com/PCHfdHz4GlDNAhBb/arcgis/rest/services/calenviroscreen50results_F_070126_gdb/FeatureServer/0

Final technical report:
https://oehha.ca.gov/sites/default/files/media/2026-06/calenviroscreen50reportf2026.pdf

## Diesel PM fields and normalization

The zipped shapefile uses `diesel` for the raw indicator and `dieselP` for its
percentile. The equivalent final ArcGIS FeatureServer fields are `Diesel_PM`
and `Diesel_PM_Pctl`.

The Python loader renames these to:

- `diesel_pm_tons_per_year`
- `diesel_pm_percentile`
- `diesel_pm_top_quintile` (`percentile >= 80`)

The shapefile uses `-999` for missing numeric values. The loader converts that
sentinel to a true null. The final release contains 9,106 tracts and nine
missing diesel-PM observations.

## Interpretation limitations

- This CES indicator estimates diesel PM **emissions** from on-road and
  non-road sources within and near populated blocks. It is not an ambient
  diesel-PM concentration measurement.
- The percentile is a relative statewide ranking for this release, not a
  health threshold or a directly measured pollution concentration.
- Missing is not zero. Missing tracts have no percentile and should display as
  unknown, not as low burden.
- The layer characterizes existing burden in the source period. It does not
  estimate future emissions from proposed data-center backup generators.
- Census-tract overlays support screening and descriptive comparisons. They
  do not establish that a data center caused the existing diesel burden.
