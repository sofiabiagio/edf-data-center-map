# CPUC PSPS frequency layer

This directory caches the California Public Utilities Commission's official
2024 and 2025 POSTSR2A submissions for PG&E, SCE, SDG&E, Liberty, PacifiCorp,
and Bear Valley Electric Service. `source_manifest.csv` records the exact CPUC
URL, SHA-256 checksum, format, and status of each source. The official 2010
Census TIGER/Line California tract file supplies the published reporting
geometry. The 2020 file remains cached only as an audit reference.

## Published metric

`code/psps_frequency_layer.py` calculates:

> **Sum of monthly maximum PSPS events affecting any one reported customer account
> (2024–2025)**

The CPUC defines `MaxEvents` as the maximum number of de-energization events
impacting any customer account in a census tract in a month. The layer first
takes the maximum across duplicate or overlapping records for each normalized
tract-month, then sums those monthly maxima across 2024–2025. This prevents
event-window layers or overlapping utility records from being counted twice.
It is a useful frequency proxy, but it is **not**:

- a count of unique PSPS events in a tract;
- a claim that one identified customer experienced the full two-year sum;
- proof that a particular data center lost power or operated generators.

## Coverage and missingness

- The four utilities with geodatabases report 2,971 positive-impact records:
  PG&E, SCE, SDG&E, and Liberty.
- Four records cannot be mapped because both geometry and tract identifier are
  null: one SDG&E 2024 record and three SCE 2025 records. Together they report
  23 customer accounts. They remain in the normalized record audit but are
  excluded from the choropleth.
- PacifiCorp's 2024 workbook explicitly says there was no PSPS event.
- The 2024 and 2025 BVES workbooks and 2025 PacifiCorp workbook contain the
  POSTSR2A template but no spatial records. Their blanks are not converted to
  zero.
- A missing tract record is never treated as zero. On request, the Folium
  helper draws non-impact/context tracts in gray with an explicit
  no-inference label.

## Geography handling

The filings predominantly use 2010 tract geography: 2,926 located records have
a utility GEOID that exactly matches the 2010 tract containing the submitted
polygon's representative point. Thirty-nine SDG&E 2025 records use newer tract
identifiers, and two Liberty records use local tract identifiers. Those 41
records are assigned to the containing 2010 tract from their submitted
geometry. Four rows lack both a usable identifier and geometry and remain
unlocatable. The published layer uses official, non-overlapping 2010 Census
polygons rather than dissolving mixed-vintage utility polygons.

SCE's 2024 geodatabase contains both the POSTSR2A feature class and a
`CES_FINAL` reference feature class with duplicate PSPS attributes. The latter
is excluded to prevent double counting.

## Rebuild and validate

From the repository root:

```bash
PYTHONPYCACHEPREFIX=/tmp/psps-pycache \
  .venv/bin/python code/psps_frequency_layer.py
```

The reusable interfaces are:

- `load_source_manifest()`
- `load_psps_records()`
- `load_psps_frequency_layer()`
- `validate_psps_layer()`
- `add_psps_frequency_layer(folium_map, ...)`
