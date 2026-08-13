# California data-center map: publication audit

Audit date: 2026-07-26

## Intended decision use

The map is designed to support defensible, exploratory comparisons between:

- proposed California data centers and their documented load, backup-generation,
  interconnection, dedicated-facility, and grid-upgrade attributes;
- CAISO transmission investments and reliability-constrained areas;
- IOU tariff jurisdictions;
- historical PSPS exposure; and
- existing diesel-PM burden.

It is not designed to prove that a particular data center caused a transmission
project, determine final cost allocation, predict generator operation, or treat
missing records as zero.

## Publication status

| Component | Status | Publication conclusion |
|---|---:|---|
| CAISO TPP geometry | Pass | All 42 published component rows map across the Board-approved plan's 38 projects. |
| Local Reliability Areas | Pass | Official CPUC polygons eliminate the need to georeference a static image. |
| IOU service territories | Pass with boundary caveat | Six CEC IOU polygons; approximate, not legal service determinations. |
| CalEnviroScreen diesel PM | Pass | Final CES 5.0 values match the live OEHHA service for all 9,106 tracts. |
| PSPS frequency | Pass after correction | Duplicate counting and mixed tract vintages were corrected. |
| Data-center markers | Pass with disclosed scope limit | All 14 CEC SPPE project rows have documented, parseable coordinates in `code/data/data_centers_corrected.csv`. |
| Integrated HTML | Pass structural tests | All layers, popups, legends, panes, and grouped controls are present. A final human browser smoke test remains advisable. |

The context layers are publication-ready. The complete map must not be
described as a comprehensive statewide data-center inventory because its
project scope is limited to CEC SPPE records.

## 1. Data-center records

### Goal

Show the projects being studied and expose enough of the underlying record on
hover/click to answer load, backup generation, interconnection, dedicated
facilities, grid upgrades, utility, and environmental-context questions.

### Source and transformation

- Source: `code/data/data_centers_corrected.csv`, compiled from linked CEC SPPE
  project pages and public dockets.
- A project row must have a docket matching `NN-SPPE-NN`.
- A point is published only when latitude and longitude parse to plausible
  California coordinates. A trailing comma in NorthTown's latitude is treated
  as a formatting artifact, not a new inferred value.
- All 14 SPPE project rows pass those rules.
- Popups retain every nonblank substantive source field, plus CEC and docket
  links.
- Each point is also spatially joined to the map's LRA, IOU, CES diesel-PM, and
  PSPS layers. A missing PSPS impact record is labeled “not treated as zero.”

### Verification and limitations

- Automated tests assert 14 project rows, 14 mappable rows, valid coordinate
  bounds, source links, and contextual joins.
- No general or provisional data-center inventory is included. The project
  layer is explicitly restricted to CEC SPPE records.
- The point represents the documented project location, not a surveyed campus
  boundary.

## 2. CAISO 2025–2026 transmission-plan geometry

### Goal

Produce a close, intelligible approximation of every scope row in the user's
TPP CSV by reusing authoritative substation and transmission geometry whenever
possible.

### Sources and transformation

- Project attributes and endpoints: `code/tpp_upgrades.csv`.
- Official plan check: CAISO Board-approved 2025–2026 Transmission Plan,
  approved May 19 and posted May 28, 2026.
- Existing substation points: committed, checksum-verified snapshot of the CEC
  ArcGIS substation service. Live access occurs only with the explicit refresh
  flag and is never a routine-build fallback.
- Existing transmission paths: repository CEC transmission GeoJSON.
- The CEC downloader first obtains the service count, discovers the real layer
  ID, downloads in deterministic object-ID order, and rejects incomplete or
  duplicate pagination.
- CAISO/CEC naming differences are handled only through explicit aliases and
  disambiguation rules; there is no fuzzy endpoint guessing.
- Three supplemental reference points are used where the CEC layer lacks an
  endpoint: DeAnza (approximate), Mira Sorrento, and Trout Canyon (approximate).

### Results

- 4,442 official CEC substations loaded from the snapshot; three supplemental points are
  added only for TPP resolution.
- 42 of 42 published component rows produce geometry:
  - 18 existing-substation upgrades;
  - one new-substation point (DeAnza);
  - 16 existing-line scopes; and
  - seven new-line scopes.
- Of the existing-line scopes, one uses an exact named transmission path, one
  uses a measured local line segment, and 12 use straight endpoint connectors.
  All six new-line scopes use schematic endpoint connectors because a final
  route is not represented in the source GIS.
- The geometry basis is visible in each project tooltip/popup.
- Two confirmed CSV omissions were corrected from the Board-approved plan:
  Lugo 230 kV CB Upgrade is reliability-driven and costs $4–5 million; Devers
  230 kV SCD Upgrade is reliability-driven and costs $124–186 million.

### Scope limitation

The Board-approved plan contains 38 projects. Some projects contain multiple
physical scope rows, which is why 38 projects become 42 mapped components. The
legend states both counts.

Straight connectors are locational approximations, not proposed rights-of-way
or construction alignments. For example, an underground or routed line can be
longer than the endpoint distance.

## 3. Local Reliability Areas

### Goal

Show California load pockets/local capacity areas without hand-georeferencing
an image.

### Source and transformation

- Official CPUC `LocalReliabilityAreas` feature service.
- Source metadata reports a last edit of 2023-01-26.
- The source has ten current polygons, and current CAISO LCR study materials
  continue to use the same ten named areas.
- Web-display copies are topology-preserving simplifications at 100 meters.

### Verification

- Ten of ten features load; all are current in the published source.
- All geometry is WGS84, polygonal, nonempty, and valid.
- Simplification reduced vertices by about 87% with roughly 0.0016% total-area
  drift.
- The tooltip says “Current in published source” and displays the source edit
  date; it does not imply the GIS was redrawn in 2026.

### Interpretation limit

An LRA is a CAISO local-capacity/reliability study area, not a direct measure of
current congestion, outage probability, or spare interconnection capacity.

## 4. IOU service territories

### Goal

Identify the IOU jurisdiction relevant to tariffs and CPUC proceedings.

### Source and transformation

- Official CEC electric load-serving-entity polygons, last edited
  2025-08-28.
- The cache preserves all 85 published LSE polygons for analysis.
- The published jurisdiction overlay is deliberately restricted to the six
  IOUs: PG&E, SCE, SDG&E, PacifiCorp, Liberty, and BVES.
- CCAs and other overlapping suppliers are not used as proxies for distribution
  wires or IOU tariff jurisdiction.

### Verification and limitation

- Six IOU polygons load with valid WGS84 polygon geometry.
- The full cache contains 59 records classified as distribution-utility
  candidates and 85 LSE records overall, but the CEC source is not a legal
  service-boundary determination.
- The tooltip and legend preserve the CEC caveat that boundaries are
  approximate. A site's actual serving utility should be verified from project
  records or the utility.

## 5. CalEnviroScreen 5.0 diesel PM

### Goal

Show the statewide diesel-PM burden as both a continuous percentile
choropleth and an explicit top-quintile overlay.

### Source and transformation

- Final OEHHA CalEnviroScreen 5.0 release dated 2026-07-01.
- Official shapefile and data dictionary are cached with checksums.
- Source `-999` values are converted to null before any classification.
- Top quintile means diesel-PM percentile greater than or equal to 80.
- The web copy is topology-preserving and simplified; source values are not
  changed.

### Verification

- 9,106 unique tract rows.
- Nine missing raw values and nine matching missing percentiles.
- 1,820 tracts at or above the 80th percentile.
- All polygons are valid.
- A full tract-by-tract comparison to the live final OEHHA feature service
  found zero raw-value mismatches, zero percentile mismatches, and zero join
  misses.

### Interpretation limit

The raw indicator is estimated diesel-PM emissions in tons per year from
on-road, area, stationary, and ocean-vessel sources, converted from a statewide
grid to tracts. It is not an ambient concentration measurement and does not
include future emissions from a proposed data center's backup generators.

## 6. PSPS frequency

### Goal

Create a statewide, tract-based heat-map-style view of how frequently customers
were affected by reported PSPS activity in 2024–2025.

### Sources

- CPUC POSTSR2A submissions for PG&E, SCE, SDG&E, Liberty, PacifiCorp, and
  BVES for 2024 and 2025.
- Official 2010 Census TIGER/Line California tract polygons.
- The manifest records exact URLs and SHA-256 hashes; every cached file
  currently matches its manifest.

### Corrected method

`MaxEvents` is the maximum number of PSPS events affecting any one customer
account within a tract in a month. The published metric:

1. normalizes records to a single, non-overlapping 2010-equivalent tract
   geography;
2. takes `max(MaxEvents)` across duplicate event-window or overlapping utility
   rows within each tract-month; and
3. sums those monthly maxima across 2024–2025.

The prior implementation incorrectly summed duplicate tract-month rows and
mixed 2010 and 2020 polygons. Both defects are fixed.

### Geography audit

- 2,926 records exactly match the submitted 2010 GEOID and containing tract.
- 39 SDG&E 2025 records use newer tract IDs and are assigned to their containing
  2010 tract.
- Two Liberty records with local identifiers are spatially assigned.
- Four records lack both usable geometry and a tract identifier; they cover 23
  customer accounts and remain in the audit but not the map.
- Published geometry exactly equals official 2010 tract geometry.
- There are zero positive-area overlaps between output polygons.

### Results and limitations

- 2,971 source records; 2,967 located.
- 1,546 output tracts with reported impact.
- Metric range: 1–15; metric sum: 3,838.
- PacifiCorp's 2024 workbook explicitly reports no PSPS event.
- Blank BVES 2024/2025 and PacifiCorp 2025 templates are not converted to zero.
- Absence from the impact layer is not evidence of zero events or complete
  utility coverage.
- This is a frequency proxy, not a count of distinct regional PSPS events, a
  claim about one named customer's two-year experience, or evidence that a
  data center operated its generators.

## 7. Integrated map behavior

- One grouped layer control organizes data centers, infrastructure,
  reliability/jurisdiction, and equity/resilience layers.
- Data centers, TPP lines, substations, and filled context polygons use explicit
  Leaflet panes. Context polygons remain below infrastructure even when toggled
  later.
- Context layers default off so users can choose one analytical mode at a time.
- Legends appear and disappear with their associated overlay.
- The generated HTML contains all 42 TPP components, all 14 SPPE data centers,
  all required layer names, and the methodology/caveat text.
- Current staged site size: about 33 MB, including lazy GeoJSON assets and
  file-preview JavaScript fallbacks. It also loads Folium/Leaflet libraries
  and Carto basemap tiles from the internet.

## 8. Verification record

Automated suite: 47 tests, all passing.

The tests cover:

- exact-versus-alias endpoint behavior and deterministic ArcGIS pagination;
- data-center filtering, popup fields, and contextual joins;
- LRA/utility counts, geometry validity, role filtering, simplification drift,
  and caveat rendering;
- CES release counts, missing-value handling, top-quintile classification, and
  Folium rendering;
- PSPS source coverage, tract-vintage normalization, duplicate suppression,
  official output geometry, metric totals, and Folium disclosure.

All Python modules compile. Static HTML checks confirm one grouped layer
control, four custom panes, every layer name, every TPP project name, all 14
mapped SPPE data-center names, and all key caveat labels.

The in-app browser blocked local-file preview in this environment, so a final
manual browser smoke test should confirm basemap loading, hover/popup behavior,
legend toggling, and acceptable performance before deployment.

## Remaining work, ranked

1. **Required before announcing publication:** deploy a Pages preview and run
   the desktop/mobile/accessibility/slow-network matrix in
   `docs/map-ux-design-plan.md`, recording cold load, largest layer time, and
   browser memory.
2. **Required repository administration:** enable Pages from GitHub Actions and
   protect `main` with the passing CI check.
3. **Optional:** move the unchanged `dist/` artifact to another static host if
   measured traffic or layer performance later exceeds Pages limits.
