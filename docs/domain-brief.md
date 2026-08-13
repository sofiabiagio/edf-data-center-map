# California Data Centers, Grid Infrastructure, Reliability, and Equity

## Domain brief for a public-facing mapping project

**Current through:** July 26, 2026  
**Research standard:** Prefer authoritative primary sources; distinguish filed/proposed facts from agency findings and analyst inference.

## Executive takeaways

1. **CEC Small Power Plant Exemption (SPPE) records are an unusually rich but incomplete data-center source.** They often disclose project coordinates or parcels, building and generator counts, generator fuel and ratings, maximum and expected load, utility provider, proposed substations/switching stations, line routes, operating assumptions, and air-quality analysis. But the SPPE concerns thermal generation—not the data center as such—and generally captures backup-generation facilities between 50 and 100 MW. It is not a census of California data centers.
2. **A backup plant's nameplate MW is not the same as the data center's grid demand or the amount that will run during every outage.** Designs commonly include redundant units, “house” generators, staged loads, and different peak versus continuous ratings. A PSPS overlapping the site establishes exposure to a utility shutoff, not actual generator dispatch or emissions.
3. **Use CalEnviroScreen 5.0 for the diesel-PM layer.** It was released July 1, 2026 and is available as a shapefile, geodatabase, CSV, and feature service. Its diesel indicator is a statewide, tract-level relative exposure proxy based on modeled emissions—not a monitor reading, health-risk estimate, or estimate of future data-center generator emissions.
4. **The CPUC's annual PSPS post-season geodatabases are the best standardized historical equity layer.** Build tract-year metrics from the utility POSTSR2A submissions, preserve utility/year coverage metadata, and state that CPUC posts the submissions without necessarily having reviewed or validated them. Do not substitute the Cal OES live outage layer; that layer expressly contains no history.
5. **A Local Reliability Area is a transmission-constrained load pocket, not a general congestion score.** It indicates an area where a minimum amount of local capacity is needed to meet reliability criteria under studied contingencies. It does not establish that a data center caused the constraint, that the facility will suffer more outages, or that a particular upgrade is attributable to it.
6. **For transmission-upgrade attribution, use evidence tiers.** An explicit CAISO or utility statement that an upgrade addresses identified data-center load is publishable as direct evidence. A project located near a cluster or within a study area is only spatial context. Geographic proximity alone should never be presented as causation.
7. **Avoid definitive “developer-paid” versus “ratepayer-paid” labels unless a tariff, agreement, CPUC/FERC decision, or project record resolves the question.** A more defensible public classification is: customer-dedicated facilities; interconnection facilities/upgrades; broader network upgrades; and cost treatment unresolved. PG&E Electric Rule 30 currently requires transmission-level applicants to advance or pre-fund specified costs, while final refunds and loan repayment remain pending in CPUC Application A.24-11-007.

## 1. How a data center receives and maintains power

A grid-supplied campus typically connects at distribution or transmission voltage through some combination of a utility line, switching station, utility or customer substation, transformers, campus switchgear, and lower-voltage distribution. Inside the facility, uninterruptible power supply equipment—often batteries—bridges the short interval between a utility interruption and generator startup. Backup generators then serve designated critical IT, cooling, safety, and “house” loads. Multiple utility feeds or transformers may improve redundancy but do not necessarily represent independent upstream grid paths.

Reliability terminology must be read carefully:

- **Grid load** is the power drawn from the utility. Filings may disclose a maximum load, expected load, critical IT load, phased load, or transformer capacity; these are not interchangeable.
- **Generator nameplate capacity** is installed generating capability. It may exceed served load because of N+1, N+2, “x-to-make-y,” reserve, maintenance, or house-generator configurations.
- **Peak and continuous generator ratings** may differ. For example, the CEC's McLaren summary reports both 2.75 MW peak and 1.93 MW continuous ratings per generator.
- **Backup-facility SPPE capacity** is not automatically the data center's electric demand. The Walsh record, for example, describes a 98 MW generating facility designed to support an 80 MW maximum building load.
- **A substation “on campus” does not establish ownership or cost responsibility.** The developer may construct a substation that is later owned and operated by the utility. The Mission College record expressly describes a developer-constructed distribution substation to be owned and operated by Silicon Valley Power.

CEC states that most data centers rely on the grid as their primary source and commonly use diesel generators for backup; those units generally operate during emergencies, testing, and maintenance and still require permits. CARB's Stationary Diesel ATCM allows appropriately permitted emergency standby engines to operate when normal service is lost for reasons beyond the facility's control, including PSPS events. New stationary emergency diesel engines over 50 brake horsepower generally face emissions standards and a 50-hour annual maintenance/testing limit under the ATCM, while emergency operation is not limited by that particular cap; local air-district permits can impose additional conditions.

**Mapping consequence:** publish separate fields for `grid_load_mw`, `critical_it_mw`, `backup_nameplate_mw`, `backup_continuous_mw`, `generator_count`, `redundancy_description`, and `source_document`. Do not collapse them into one “capacity” field.

Sources: [CEC Data Centers overview](https://www.energy.ca.gov/programs-and-topics/topics/data-centers); [CARB Emergency Backup Generators](https://ww2.arb.ca.gov/our-work/programs/emergency-backup-generators/about); [CARB Stationary Diesel ATCM](https://ww2.arb.ca.gov/our-work/programs/stationary-diesel-atcm); [CARB ATCM regulation order](https://ww2.arb.ca.gov/sites/default/files/classic/diesel/ag/documents/finalreg112807.pdf); [CEC McLaren](https://www.energy.ca.gov/powerplant/backup-generating-system/mclaren-backup-generating-facility); [CEC Walsh](https://www.energy.ca.gov/powerplant/backup-generating-system/walsh-data-center); [CEC Mission College](https://www.energy.ca.gov/powerplant/backup-generating-system/mission-college-data-center). Accessed July 26, 2026.

## 2. CEC Small Power Plant Exemptions

### What the process is

The CEC has siting authority over thermal power plants of 50 MW or more. Under Public Resources Code section 25519(c), an eligible facility below the statutory ceiling may seek an SPPE. CEC describes the currently relevant band as thermal facilities between 50 and 100 MW. CEC acts as the CEQA lead agency and may grant an exemption if it finds no substantial adverse impact on the environment or energy resources. An exemption removes the project from CEC certification; it is **not final construction or operating approval**. Local land-use authorities, air districts, and other agencies retain their respective permitting roles.

### What the filings can reliably reveal

Treat these as high-value source documents, but record provenance at the field level:

- applicant/project owner and docket number;
- project address, parcel numbers, site plan, and coordinates;
- procedural status and dated milestones;
- proposed building count, floor area, phases, and campus footprint;
- generator count, manufacturer/model where disclosed, fuel, individual ratings, aggregate rating, redundancy, and proposed use;
- fuel storage and modeled testing/maintenance schedules;
- maximum, expected, or critical IT load, if specifically stated;
- named utility, proposed service voltage, substation/switching-station configuration, and line route or point of interconnection, if specifically stated;
- air-quality modeling, health-risk assessment, mitigation, and agency comments;
- alternatives and cumulative-impact discussion.

The evidentiary label should follow the document:

- **Applicant filing:** “applicant states/proposes.”
- **CEC staff environmental document:** “CEC staff analyzed/found.”
- **Commission decision:** “CEC approved/exempted,” with decision date.
- **Later local or air-district permit:** use that later record for final permitted equipment and operating conditions.

### What the SPPE universe misses or can misstate

- Data centers whose aggregated thermal backup generation is below 50 MW.
- Projects using configurations outside the SPPE band, including larger thermal plants that use another CEC pathway.
- Projects not using thermal backup generation.
- Existing data centers that never triggered this process.
- Projects that are confidential, abandoned before filing, locally approved under another path, or materially revised later.
- Operational status. “Exempted” means the exemption was granted, not necessarily that the data center was built, energized, fully leased, or operating at stated load.
- Actual electricity consumption and actual emergency-generator hours.
- Final interconnection scope, ownership, and cost allocation, unless later records confirm them.

The CEC's own project records illustrate the distinction. Sequoia identifies 54 diesel units and a 100 MVA on-site substation; AVAIO Pittsburg states its backup plant would not interconnect to the grid; RB Inyokern states its backup plant would not export or provide grid support and describes a customer-dedicated 115/34.5 kV substation; San Jose Data Center describes a materially different renewable-natural-gas design that contemplated load shedding, demand response, and behind-the-meter resource-adequacy services.

**Recommended confidence rule:** CEC docket facts are high confidence as descriptions of what was filed or approved on the date of the document. They are not high confidence as current built conditions until corroborated by a later permit, inspection, utility energization evidence, or authoritative operational record.

Sources: [CEC Data Centers overview](https://www.energy.ca.gov/programs-and-topics/topics/data-centers); [CEC San José Data Center 04](https://www.energy.ca.gov/powerplant/backup-generating-system/san-jose-data-center-04); [CEC Sequoia](https://www.energy.ca.gov/powerplant/backup-generating-system/sequoia-data-center); [CEC AVAIO Pittsburg](https://www.energy.ca.gov/powerplant/backup-generating-system/avaio-pittsburg-backup-generating-facility-pbgf); [CEC RB Inyokern](https://www.energy.ca.gov/powerplant/backup-generating-system/rb-inyokern-data-center); [CEC San Jose Data Center](https://www.energy.ca.gov/powerplant/backup-generating-system/san-jose-data-center). Accessed July 26, 2026.

## 3. CPUC, utility tariffs, and PG&E Electric Rule 30

### Jurisdiction

The CPUC regulates privately owned electric utilities, including PG&E, Southern California Edison, San Diego Gas & Electric, Bear Valley Electric Service, Liberty, and PacifiCorp. It approves IOU retail rates, service rules, and distribution cost recovery and performs safety oversight. Publicly owned utilities such as LADWP, SMUD, and Silicon Valley Power are principally governed by their local boards; CPUC does not set their retail rates, although it has specified safety roles.

Transmission jurisdiction is split. CAISO operates and plans much of the high-voltage grid, participating transmission owners own facilities, and FERC primarily regulates transmission rates and associated cost recovery. CPUC participates in FERC proceedings on behalf of California ratepayers. Consequently, “CPUC-regulated utility territory” does not mean every relevant transmission-cost decision occurs at CPUC.

Do not confuse **load interconnection** with **generator interconnection**. CPUC Electric Rule 21 concerns generating or storage facilities interconnecting to an IOU system; it is not the default rule for a data center merely requesting retail load service. Applicable extension, special-facilities, service-voltage, and rate-schedule rules vary by utility and service configuration.

### PG&E Electric Rule 30: precise current description

Electric Rule 30 is **not itself a CPUC rulemaking**. It is PG&E's tariff for retail service at transmission voltage, considered in **CPUC Application A.24-11-007**. Decision D.25-07-039 partially authorized interim implementation. The current tariff, effective December 4, 2025 through Advice 7772-E, applies to nonresidential applicants served from 50 kV through 230 kV, with PG&E determining service voltage. PG&E's large-load requests at lower voltage remain outside Rule 30.

Under the interim rule:

- PG&E generally plans, designs, and engineers the transmission facilities.
- Facilities installed under the rule are generally PG&E-owned, operated, and maintained, with stated exceptions for certain applicant structures/enclosures.
- The applicant must advance project-specific estimated costs for “Transmission Service Facilities,” “Transmission Interconnection Upgrades,” and “Transmission Interconnection Network Upgrades” (Types 1–3), then pay actual costs.
- The applicant must provide a pre-funding loan for 100 percent of “Transmission Network Upgrades” (Type 4).
- Final refund treatment for Types 1–3, interest, and repayment of the Type 4 loan are reserved for the final CPUC decision in A.24-11-007.
- Applicant-requested special facilities carry incremental costs and ownership charges.
- An applicant-build option exists for eligible facilities, but accepted facilities are transferred to PG&E; underground facilities and specified work inside existing PG&E facilities are excluded.

Therefore, “the developer pays upfront” is supported under interim Rule 30; “the developer permanently bears all costs” is not. Ownership, construction responsibility, initial funding, refundability, loan repayment, rate-base inclusion, and ultimate incidence are different questions.

Sources: [CPUC Regulatory Services](https://www.cpuc.ca.gov/regulatory-services); [CPUC Electric Rates](https://www.cpuc.ca.gov/industries-and-topics/electrical-energy/electric-rates); [CPUC Transmission Rates and FERC Proceedings](https://www.cpuc.ca.gov/industries-and-topics/electrical-energy/electric-costs/electric-transmission-rates-and-ferc-proceedings); [CPUC Rule 21](https://www.cpuc.ca.gov/Rule21); [CPUC Rule 30 announcement, July 24, 2025](https://www.cpuc.ca.gov/news-and-updates/all-news/cpuc-streamlines-electric-grid-connections-for-high-energy-users-like-data-centers-and-ev-chargers); [PG&E current Electric Rule 30 tariff](https://www.pge.com/tariffs/assets/pdf/tariffbook/ELEC_RULES_30.pdf); [PG&E tariff book](https://www.pge.com/tariffs/en.html). Accessed July 26, 2026.

## 4. Dedicated facilities, network upgrades, and defensible cost language

For the map, classify physical scope independently from financing:

1. **Customer-side/dedicated campus facilities:** equipment serving the site behind or at the service point, such as campus switchgear, customer transformers, backup generators, and some customer substations. Evidence may show sole use, but ownership can still transfer to a utility.
2. **Service/interconnection facilities:** the line, bay, switching equipment, and substation work needed to connect the customer physically.
3. **Interconnection network upgrades:** new facilities needed to connect into the existing transmission system or mitigate connection impacts.
4. **Broader network upgrades:** reinforcement of the existing grid needed to provide adequate service or mitigate system impacts and potentially capable of benefiting other users.
5. **Shared/multi-driver planning project:** a CAISO-approved project addressing aggregate forecast load, reliability, policy, economic, or multiple benefits.

Recommended public labels:

- “Applicant/customer-dedicated facility” only when the source expressly says dedicated or sole-use.
- “Utility-owned facility funded initially by applicant” when both facts are documented.
- “Broader network upgrade required to serve/mitigate the load” when a study or tariff record supports it.
- “Potential for costs beyond the developer” only when refund, repayment, rate-base, Transmission Access Charge, or shared-cost treatment is documented or expressly unresolved.
- “Final cost responsibility unresolved” for interim Rule 30 facilities absent a controlling final decision or agreement.

Avoid:

- “Ratepayers paid” based only on utility ownership.
- “Developer paid” based only on on-site location or applicant construction.
- “Data-center upgrade” based only on proximity.
- Treating a utility's capital cost estimate as proof of final rate recovery.

## 5. CAISO transmission planning and upgrade attribution

CAISO's annual Transmission Planning Process tests the ISO-controlled grid under reliability standards and evaluates reliability-, policy-, and economic-driven needs and solutions. Projects can have multiple benefit streams. The 2025–2026 Board-approved plan recommends 38 projects and states that more than half of the projects and estimated $6.7 billion cost are driven by forecast load growth. The plan identifies large loads, including data centers, among statewide load-growth drivers and points to major Greater Bay Area reinforcements.

The load input is a forecast, not a list of executed customer commitments. It can combine building and transportation electrification, ordinary growth, manufacturing, and large loads. A project may also solve multiple contingencies or provide policy and economic benefits. Later forecasts, topology, generation assumptions, project withdrawals, or alternative solutions can change the result.

### Publishable attribution ladder

| Level | Evidence | Safe public wording |
|---|---|---|
| A — explicit | CAISO final plan/study or utility presentation expressly names data-center load and links it to the need or project | “CAISO identifies forecast data-center load as a driver of this upgrade.” |
| B — quantified but aggregated | Study identifies large-load MW or a study-area load increase, but not the named facility/cluster | “The upgrade responds to forecast load growth that includes large loads/data centers; the public record does not isolate this site's share.” |
| C — spatial/temporal association | Upgrade and data-center cluster overlap, with no causal statement | “The project is geographically near/within the same study area; causation is not established.” |
| D — no evidence | Proximity only or mismatched timing | Show only as separate layers; make no attribution claim. |

Track citations down to plan page/table and distinguish “recommended,” “approved,” “under development,” “on hold,” and “completed.” The strongest workflow is to search the final plan and appendices for “data center,” “large load,” the substation name, and the local study area, then check utility presentations and CPUC/FERC filings. Do not infer project causation from a nearest-neighbor spatial join.

Sources: [CAISO 2025–2026 TPP library](https://www.caiso.com/library/2025-2026-transmission-planning-process); [Board-approved 2025–2026 Transmission Plan](https://www.caiso.com/documents/board-approved-2025-2026-transmission-plan.pdf); [CAISO approval announcement](https://www.caiso.com/about/news/news-releases/iso-board-of-governors-approves-2025-2026-transmission-plan). Accessed July 26, 2026.

## 6. Local Reliability Areas and “load pockets”

CAISO's Local Capacity Technical Study determines the minimum capacity needed in identified transmission-constrained load pockets—Local Capacity Areas—to satisfy mandatory reliability standards. These areas historically relied on local generation to supplement limited transmission import capability. The study applies NERC, CAISO, and participating-transmission-owner reliability criteria and analyzes contingencies.

The LRA layer is valuable because it gives a defensible boundary for the statement “this site lies within a CAISO/CPUC-mapped local reliability area.” It does **not** by itself mean:

- the area has high market congestion at all times;
- the local utility distribution circuit is constrained;
- the site has poor retail reliability or frequent outages;
- the data center caused the local requirement;
- a new transmission project is needed because of that data center; or
- backup generators will operate more frequently.

Use a current LRA boundary with a study year/version field. The CPUC GIS server publishes a `LocalReliabilityAreas` FeatureServer, and California Open Data/CEC catalog entries provide the state layer. Boundaries and sub-areas can change with topology, resource retirements, and study assumptions.

Sources: [CAISO 2026 Local Capacity Requirement Study Manual](https://stakeholdercenter.caiso.com/InitiativeDocuments/DraftStudyManual-2026LocalCapacityRequirements.pdf); [CPUC GIS Hosted Services directory](https://gis.cpuc.ca.gov/server/rest/services/Hosted); [California Open Data search results for Local Reliability Areas](https://lab.data.ca.gov/datasets?q=Electric&tag=Electric). Accessed July 26, 2026.

## 7. PSPS data and backup-generator implications

The CPUC requires IOUs to file post-event and annual post-season reports. The annual POSTSR2A geospatial submission is organized by census tract and month and includes fields such as:

- maximum number of de-energization events affecting any customer account;
- maximum, minimum, and median account-level hours de-energized;
- total affected accounts and summed customer-hours;
- corresponding CARE/FERA, Medical Baseline, and access-and-functional-needs measures.

The required schema is designed to align tract identifiers with CalEnviroScreen geography. CPUC's report page provides annual utility filings, but availability and format vary by utility/year, and posted submissions should not be represented as CPUC-validated unless CPUC says it reviewed them.

### Recommended aggregation and confidence

1. **Primary metric: `psps_ever_impacted` by tract and covered period.** Set true when an authoritative POSTSR2A record reports impact. This is the clearest high-confidence public metric, subject to disclosed utility/year coverage.
2. **Frequency proxy: `max_customer_event_exposure`.** Sum monthly `MaxEvents` within tract-year only if the schema remains consistent. Label it exactly as the maximum number of PSPS events affecting any customer account—not “events in the tract.” Summing across years is acceptable with the same label and complete coverage.
3. **Duration proxy: `max_customer_hours` and `median_customer_hours` by month/year.** Preserve the account-level definitions. Do not describe a tract as shut off continuously for the sum of maximum hours.
4. **Burden metric:** retain total customer-hours and impacted-account counts separately. Do not calculate an “average outage duration” unless the denominator is demonstrably account-event observations rather than unique accounts.
5. **Coverage table:** for every map release, publish utility, calendar year, file date, schema/version, tract vintage, and review status. Missing records must be `unknown/not available`, never zero.
6. **Event-level polygons:** where official post-event geodatabases are available and standardized, count distinct event IDs intersecting the site as a separate measure. Do not merge this silently with POSTSR2A's customer-level maximum.

Suggested map confidence:

- **High:** tract ever impacted, directly from standardized filing with complete year/utility coverage.
- **Medium:** frequency/duration proxy with exact schema-derived label.
- **Low/not publishable as fact:** estimated generator runtime or emissions inferred from PSPS overlap alone.

Why the last distinction matters: an overlapping PSPS does not prove the facility was energized, served by the de-energized circuit, without an unaffected secondary feed, or operating generators at full nameplate. The defensible statement is: “The site is in a tract with reported PSPS exposure; appropriately permitted standby generators may operate during loss of utility service.” Actual dispatch requires generator logs, permit compliance records, facility disclosures, or other direct evidence.

The Cal OES “Power Outage Incidents” GIS layer is useful for current situational awareness but explicitly says it updates frequently and contains only the most recent outages, not history. It should not be used to calculate historical PSPS frequency.

Sources: [CPUC utility PSPS reports](https://www.cpuc.ca.gov/consumer-support/psps/utility-company-psps-reports-post-event-and-post-season); [CPUC PSPS overview/dashboard entry](https://www.cpuc.ca.gov/consumer-support/psps); [CPUC power-outage maps](https://www.cpuc.ca.gov/consumer-support/power-outage-maps); [CARB backup engines during PSPS](https://ww2.arb.ca.gov/resources/documents/use-back-engines-electricity-generation-during-public-safety-power-shutoff); [Cal OES Power Outage Incidents](https://test.lab.data.ca.gov/dataset?name=power-outage-incidents). Accessed July 26, 2026.

## 8. CalEnviroScreen 5.0 diesel particulate matter

OEHHA released CalEnviroScreen 5.0 on July 1, 2026. Use the final 5.0 data, not the draft or 4.0, for a new publication. The state portal provides a shapefile, geodatabase, CSV, Excel file, data dictionary, and feature layer at census-tract granularity.

The diesel-PM exposure indicator uses CARB emissions estimates in tons/year from on-road, area, stationary point, and ocean-going vessel sources, generally using 2021 or 2022 source data. CARB's gridded 1 km by 1 km emissions are converted to census tracts, with adjustments for cross-border sources affecting San Diego and Imperial counties. OEHHA ranks tract indicator scores to percentiles.

For the requested “top quintile,” use the final dataset's **diesel-PM indicator percentile >= 80**, not the overall CalEnviroScreen percentile and not the separate statutory disadvantaged-community designation. Publish both raw indicator and percentile when available.

Important limitations:

- It is a relative statewide screening indicator, not a site-specific monitor reading.
- It estimates emissions-related exposure and does not model all neighborhood-scale meteorological dispersion.
- It can smooth sharp gradients near roads or other sources.
- Its underlying emissions years predate a 2026 map release.
- It is not a forecast of future data-center generator emissions.
- A site's census-tract value does not establish the incremental health risk caused by that facility.
- “Top diesel-PM quintile” is not synonymous with “disadvantaged community.” The latter uses an overall cumulative-impact designation and, as of July 2026, CalEPA's 2026 update process should be checked for final status before publishing a DAC flag.

Safe wording: “The proposed site falls in a census tract in the highest statewide quintile of CalEnviroScreen 5.0's diesel-PM exposure indicator.” Avoid: “The data center is causing top-quintile diesel pollution.”

Sources: [OEHHA CalEnviroScreen 5.0](https://oehha.ca.gov/calenviroscreen/report/calenviroscreen-50); [OEHHA diesel-PM indicator](https://oehha.ca.gov/calenviroscreen/fact-sheet/diesel-particulate-matter); [OEHHA model and scoring](https://oehha.ca.gov/calenviroscreen/model-scoring); [CalEnviroScreen 5.0 download](https://lab.data.ca.gov/dataset/calenviroscreen-5-0); [CalEPA environmental-justice designations](https://calepa.ca.gov/envjustice/). Accessed July 26, 2026.

## 9. California IOU service territories

California's CPUC-jurisdictional electric IOUs are PG&E, SCE, SDG&E, Bear Valley, Liberty, and PacifiCorp. The CEC publishes electric utility service-area GIS data and a six-IOU layer. Its statewide service-area layer also captures publicly owned utilities, which is essential around Santa Clara/Silicon Valley Power, LADWP, SMUD, and other municipal territories.

Use the all-utility layer first, then derive `utility_ownership_type` and `cpuc_rate_jurisdiction`. A data center in a municipal territory should not be assigned the surrounding IOU merely because the IOU owns nearby transmission. Likewise, a CCA changes the generation provider but generally not the incumbent distribution utility territory.

CEC metadata warns that service-area boundaries are approximate; contact the load-serving entity for definitive territory. Point-in-polygon assignment is therefore high confidence away from boundaries and provisional near overlaps, gaps, municipal enclaves, or parcel edges. Preserve the dataset version and consider a manual utility confirmation for every project near a boundary.

Recommended fields:

- `distribution_utility`
- `utility_type` (IOU/POU/cooperative/other)
- `cpuc_rate_regulated` (yes/no/partial or safety-only)
- `generation_provider` (if known; separate from wires utility)
- `service_territory_source_date`
- `boundary_confidence`
- `source_confirmation`

Sources: [CEC Energy Maps and Spatial Data](https://www.energy.ca.gov/data-reports/energy-maps-and-spatial-data); [California Open Data electric layers](https://lab.data.ca.gov/datasets?q=Electric&tag=Electric); [CEC statewide service-area FeatureServer](https://services.arcgis.com/KkJhFbLnXVqahKz2/arcgis/rest/services/Electric_Utility_Service_Areas/FeatureServer/0); [CPUC Electric Costs](https://www.cpuc.ca.gov/industries-and-topics/electrical-energy/electric-costs); [CPUC Electric Rates](https://www.cpuc.ca.gov/industries-and-topics/electrical-energy/electric-rates). Accessed July 26, 2026.

## 10. Recommended public-facing evidence model

Every mapped assertion should carry:

- `value`
- `value_type` (proposed, approved, permitted, built, operating, modeled, inferred)
- `source_agency`
- `source_title`
- `source_url`
- `source_date`
- `accessed_date`
- `document_page`
- `confidence` (high/medium/context-only)
- `notes`

Recommended claim rules:

- **High confidence:** direct agency/utility statement, final permit/decision, or unambiguous GIS join to an authoritative boundary.
- **Medium confidence:** applicant statement not independently confirmed; standardized self-reported utility data; spatial join near a boundary; aggregate forecast that includes data centers but does not isolate a facility.
- **Context-only:** proximity, temporal coincidence, or analyst-created cluster association.

For a nonprofit publication, display context-only relationships visually but suppress causal prose. Keep an internal audit table so every popup sentence can be reproduced from a cited source.

## 11. 80/20 research priorities

### Do now

1. Load final CalEnviroScreen 5.0 and flag diesel-PM percentile >= 80.
2. Ingest available standardized POSTSR2A files; build an explicit utility-year coverage matrix before calculating statewide metrics.
3. Add current CEC all-utility service territories and classify IOU versus POU.
4. Add current Local Reliability Areas with study year/version.
5. Normalize SPPE records into separate load, generation, substation, interconnection, status, and provenance fields.
6. Review CAISO projects using the attribution ladder and publish only Levels A–B as data-center-related claims.
7. Add a simple facilities-scope field: dedicated/customer-side, interconnection, broader network, shared/multi-driver, unresolved.

### Defer unless a particular project is especially important

- reconstructing every confidential utility interconnection study;
- estimating actual generator dispatch from PSPS geography;
- estimating project-specific diesel emissions without operating logs and permit conditions;
- declaring final ratepayer incidence from ownership or location;
- attributing CAISO upgrades through proximity alone;
- resolving every service-territory edge case statewide;
- exhaustive searches for all sub-50 MW data centers.

This approach captures the strongest public value—where facilities are proposed, how large and polluting their backup systems could be, which communities and grid areas overlap them, which utility rules apply, and where official records connect load growth to upgrades—without converting incomplete public records into false precision.
