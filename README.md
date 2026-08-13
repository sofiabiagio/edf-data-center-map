# California Data Center Infrastructure Map

This repository builds a static Folium/Leaflet map of California Energy
Commission Small Power Plant Exemption (SPPE) data-center projects and selected
grid, reliability, environmental, utility, and outage context. It intentionally
does not publish a general inventory of California data centers.

Public site: `https://<organization>.github.io/edf-data-center-map/` (replace
`<organization>` after the repository is created and Pages is enabled).

## Local setup

Python 3.11 is the supported baseline.

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --requirement requirements.txt
bash scripts/build_site.sh
python -m http.server --directory dist 8000
```

Open `http://localhost:8000`. The build writes only `dist/index.html`,
`dist/.nojekyll`, and lazy-loaded assets under `dist/data/web/`. The production
site still needs internet access for Carto basemap tiles and the Leaflet assets
that Folium references through CDNs.

The preserved test command is:

```bash
python -m unittest discover -s code/tests -v
```

## Repository structure

- `code/` — map builder, UI, tests, normalized source tables, and cached public
  data needed for a network-independent routine build.
- `scripts/build_site.sh` — clears only `dist/`, builds, tests, and validates.
- `scripts/validate_site.py` — checks paths, referenced assets, GeoJSON,
  publication copy, per-file size, and the 50 MB artifact budget.
- `.github/workflows/` — pull-request CI and protected Pages deployment.

The research corpus, virtual environments, temporary files, and the former
non-SPPE inventory are outside this repository and must never be copied in.

## Data sources and reuse terms

The code is MIT-licensed. Source data retain their source terms and attribution:

| Included data | Source | Reuse status / terms |
|---|---|---|
| SPPE projects | [CEC Data Centers](https://www.energy.ca.gov/programs-and-topics/topics/data-centers) and linked public dockets | California government records; attribution and source links are retained. The State says its website information is generally public domain unless otherwise indicated. |
| Substations and transmission | CEC public ArcGIS services | California public data; source attribution is retained. Utility boundaries and infrastructure locations are approximate and are not legal determinations. |
| Local Reliability Areas and PSPS reports | CPUC public ArcGIS and regulatory submissions | California public records; attribution and reporting limitations are retained. |
| CalEnviroScreen 5.0 | [California Open Data](https://lab.data.ca.gov/dataset/calenviroscreen-5-0) / OEHHA | The California Open Data portal identifies its data as public domain. |
| Census tract geometry | U.S. Census Bureau TIGER/Line® | U.S. government work; reproducible with Census attribution. Boundaries are statistical, not legal land descriptions. |
| Transmission plan project table | [CAISO 2025–2026 TPP](https://stakeholdercenter.prod.caiso.com/RecurringStakeholderProcesses/2025-2026-Transmission-planning-process) | CAISO permits use of most public website materials when proprietary notices remain intact and CAISO is credited; this repository includes attribution and tabular facts, not copies of plan PDFs. |

Relevant terms: [California Open Data licenses](https://lab.data.ca.gov/licenses),
[State conditions of use](https://handbook.data.ca.gov/conditions-of-use/),
[Census TIGER/Line](https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html),
and [CAISO terms](https://www.caiso.com/privacy-terms-of-use).

Before adding a dataset, record its publisher, canonical URL, retrieval date,
checksum where practical, transformation, limitations, and reuse terms. Do not
assume the repository's MIT license applies to third-party data.

## Publication caveats

- This is the mapped CEC SPPE inventory, not a comprehensive census of data
  centers. SPPE status does not establish that a project was built or operates
  at its stated load.
- Backup-generation nameplate capacity is not the same as grid demand or actual
  generator use.
- Spatial overlap or proximity does not establish that a data center caused a
  transmission project, pollution burden, outage, or cost allocation.
- A missing PSPS record is not treated as zero.
- TPP connector geometries may be schematic rather than surveyed routes.

## Updating data

Update the cited source table in `code/data/data_centers_corrected.csv`, retain
only documented CEC SPPE records, then run `bash scripts/build_site.sh`. Tests
require the generated site to contain neither the removed inventory label nor
its former provisional-warning copy.

Routine builds use `code/data/substations_source.geojson` and verify it against
`code/data/substations_source_manifest.json`; they never silently access the
live service. To prepare an explicit refresh for review:

```bash
python code/build_phase_zero_map.py \
  --refresh-substations \
  --output-dir dist
python scripts/validate_site.py dist
```

Review the feature-count and checksum change, run the full test suite, and merge
the snapshot only through a pull request. A refresh must not deploy directly.

## CI, deployment, and rollback

Pull requests and pushes run the complete build and upload `dist/` as a workflow
artifact. A push to `main` separately builds the same artifact, uploads only
`dist/`, and deploys through the `github-pages` environment. Actions are pinned
to full commit SHAs and Dependabot proposes dependency updates.

After the first push, set Pages source to **GitHub Actions**, keep workflow
permissions read-only by default, and protect `main`: require pull requests and
the `test-build` check, and block force pushes. The deployment job alone receives
`pages: write` and `id-token: write`.

To roll back, select a known-good commit, create a revert pull request, merge it,
and let the Pages workflow redeploy that commit's rebuilt artifact. For an urgent
operational rollback, use the workflow dispatcher from a branch containing the
known-good tree, then follow with a reviewed revert on `main`.

The initial artifact budget is 50 MB, below GitHub Pages' documented 1 GB site
limit. Complete desktop/mobile browser QA and record cold-load measurements
before announcing the public URL.

## Ownership

Maintainer: Sofia Biagio
