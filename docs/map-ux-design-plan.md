# California Data Center Map — UX and Cartographic Design Plan

**Status:** implemented; retained as the publication QA and design reference  
**Prepared:** July 26, 2026  
**Product goal:** make a publication-grade map that helps a first-time reader answer the project's substantive questions quickly, while preserving full control and source detail for expert users.

## 1. The product decision

The map should not open as a catalog of every available layer. It should open as a guided analytical tool.

Build one compact control shell with two tabs:

1. **Guided views** — one-click combinations of layers, legends, styles, and project-detail fields organized around the questions the map can answer.
2. **Build your own** — complete layer access for expert exploration.

The visual system should be **quiet editorial cartography**:

- neutral interface and low-saturation basemap;
- data centers and evidence layers in the foreground;
- existing infrastructure as context, not the visual subject;
- one stable semantic color/shape/pattern per topic;
- plain-language definitions, source dates, and limitations;
- no claim communicated by color alone;
- no layer included in a legend unless it is currently visible.

This is the best 80/20 direction. It resolves the current clutter, same-color choropleths, oversized popup, and long layer menu together instead of polishing each symptom independently.

## 2. Evidence from the current build

The present code establishes a sound data foundation, but the interface has publication-level usability gaps:

- Data centers, all substations, all transmission lines, and TPP upgrades are on by default.
- Approximately 4,445 substations and the statewide transmission network compete with the analytical layers.
- Existing transmission is dark and heavy: up to 5 px at 0.70 opacity.
- Diesel PM and PSPS both use nearly identical yellow–orange–red fills at similar opacity. The layer drawn last visually replaces the other.
- The PSPS map uses discrete classes, but its custom legend shows a continuous gradient.
- The data-center marker radius is 7 px, or about 14 px in diameter. A 12 px minimum is therefore already met; visibility is being reduced mainly by clutter, contrast, and overlap.
- Clicking a data center opens a table of every nonblank field in a popup up to 560 px wide.
- The fixed bottom-left legend and expanded top-right layer control have no collision strategy.
- The staged site is about 33 MB. Heavy GeoJSON layers are lazy-loaded; paired
  JavaScript fallbacks preserve direct local-file preview.
- Census geometry is embedded twice for the two diesel presentations.
- The document disables user scaling and lacks a meaningful page title, language attribute, equivalent project list, and reliable keyboard/touch access to map features.

The publication audit confirms the PSPS layer contains 1,546 tracts with reported impact and an observed metric range of **1–15** for 2024–2025. Missing impact records are not valid zeros.

## 3. Information architecture

### 3.1 Control shell

Place one compact, responsive control card at the upper right on desktop. It contains:

- tabs for **Guided views** and **Build your own**;
- the active view name;
- a one-sentence question the view answers;
- view or layer controls;
- **Reset view**, **Reset map**, and **Copy link** actions;
- a clear collapsed state.

Use real accessible tab semantics and visible focus states. Keep all actions available by keyboard and touch.

On mobile, convert the control card into a bottom sheet. Do not stack multiple fixed panels over the map.

### 3.2 Guided views

Use four views initially. Do not add more until user testing shows that a distinct analytical question is missing.

| View | Default visible layers | Primary question |
|---|---|---|
| **Overview** | Data centers; TPP upgrades; restrained basemap | Where are proposed data centers and planned transmission investments? |
| **Grid & reliability** | Data centers; TPP upgrades; LRA boundaries; decluttered, zoom-dependent transmission and substations | Are projects near constrained reliability areas or documented grid work? |
| **Equity & resilience** | Data centers; diesel PM percentile; PSPS history using an orthogonal encoding | Where do backup generation, existing diesel burden, and reported shutoff exposure overlap? |
| **Utility & upgrade evidence** | Data centers; IOU territories; TPP upgrades | Which utility jurisdiction applies, and what do project records say about dedicated facilities or broader grid upgrades? |

Each view must:

- apply its documented layers and styles with one action;
- update the legend;
- update the summary shown for a selected data center;
- preserve the current map center and zoom after the first selection;
- keep data centers visible unless the user explicitly hides them;
- state what the view can and cannot establish;
- show **“[View name] · customized”** if the user changes its default layers.

Do not create a fifth “backup generation” view initially. Backup generation is central to Equity & resilience and remains a key project fact in every other view.

### 3.3 Build your own

Group the complete controls as:

- **Projects**
- **Grid infrastructure**
- **Reliability and jurisdiction**
- **Environmental and outage context**

Add:

- **Clear contextual layers**
- **Restore this view**
- **Show all transmission**
- **Show all substations**

Treat alternative representations of the same measure as radio choices:

- Diesel PM: **Percentile** or **Top quintile**
- PSPS: **Frequency classes**; any future alternate representation should be mutually exclusive with it

Diesel PM and PSPS must remain simultaneously selectable. Their comparison is a core use case.

## 4. Exact visual grammar

Every topic receives a stable visual identity across all views.

| Topic | Primary encoding | Role |
|---|---|---|
| Data centers | Teal circles, white casing, dark teal edge | Primary point evidence |
| TPP upgrades | Burnt orange; solid existing-line work, dashed schematic/new line; diamond points | Primary grid evidence |
| Existing transmission | Thin, low-opacity blue-gray lines | Context |
| Existing substations | Small muted points; emphasized only when relevant | Context |
| Local Reliability Areas | Violet/charcoal dashed boundary with little or no fill | Analytical boundary |
| IOU territories | Very light categorical fills plus labeled boundaries | Jurisdiction |
| Diesel PM | Purple sequential tract fill | Existing pollution burden |
| PSPS | Blue/cyan patterned overlay in the combined view | Reported shutoff exposure |
| Missing/unreported | Neutral blank or gray pattern, explicitly labeled | Missingness, never zero |

### 4.1 Diesel PM and PSPS together

The two current YlOrRd fills cannot be compared. Opacity sliders alone would only create ambiguous blended colors.

Use:

- **Diesel PM:** six-class purple sequential fill.
- **PSPS in Equity & resilience:** blue/cyan diagonal hatch or dot pattern, with pattern density tied to frequency class.
- Place the pattern and diesel fill in separate deterministic panes.
- Give both layers an on-hover outline change without increasing fill opacity enough to hide labels or data centers.

Recommended diesel family, subject to final contrast and color-vision testing:

`#f2f0f7`, `#dadaeb`, `#bcbddc`, `#9e9ac8`, `#756bb1`, `#54278f`

If performant SVG patterns prove too brittle, use this fallback:

- PSPS as a blue sequential fill;
- diesel top-quintile tracts as a dark-plum outline or hatch;
- do not stack two continuous fills.

Do not use a nine-cell bivariate choropleth as the default. It is compact but substantially harder to learn. Consider a swipe or side-by-side comparison only after the core interface is working.

### 4.2 PSPS terminology and quantification

Remove **“frequency proxy”** from the primary control label. It is technically cautious but not self-explanatory.

Use this short label:

> **Reported PSPS frequency, 2024–2025**

Use this definition in the legend's expanded explanation:

> For each tract and month, this measure takes the largest number of PSPS events affecting any one reported customer account, then sums those monthly values across 2024–2025.

Show:

- observed mapped range: **1–15**;
- six explicit classes: **1**, **2**, **3–4**, **5–7**, **8–11**, **12–15**;
- a distinct **No reported impact record / coverage not established** category;
- reporting period: **2024–2025**;
- the limitation: this is not a count of distinct regional outages, not the history of one identified customer, and not proof that a data center operated backup generators.

The final class breaks should be generated from one shared configuration used by both the map and legend. Never hand-code a gradient that differs from the actual map classes.

### 4.3 Diesel PM legend

Show:

- **0–100 percentile**;
- ticks at 0, 20, 40, 60, 80, and 100;
- a visibly marked **80th-percentile** threshold;
- the top-quintile label as **“80th–100th percentile”**;
- missing data as a distinct category.

Keep raw tons/year in tract details, not the main legend.

### 4.4 Existing infrastructure

Do not clip infrastructure to LRA polygons. Transmission corridors and substations outside an LRA may supply it; clipping would create a substantively misleading absence.

Declutter by relevance and zoom:

| Map scale | Default infrastructure |
|---|---|
| Statewide / Overview | TPP upgrades; optionally a very faint ≥230 kV backbone; no general substation carpet |
| Statewide / Grid & reliability | LRA boundaries; TPP upgrades; ≥230 kV lines; TPP endpoint substations |
| Regional, approximately z8+ | Add 115–229 kV lines |
| Local, approximately z10+ | Add lower-voltage lines and ordinary substations |
| Selected data center | Highlight its documented point of interconnection and related named substation; mute unrelated context |

Retain complete statewide infrastructure in Build your own.

Initial style target for existing transmission:

- high voltage: about 2.25 px;
- medium voltage: about 1.5 px;
- lower voltage: about 1 px;
- opacity: approximately 0.25–0.40;
- hover/selection temporarily strengthens the line;
- TPP upgrades remain approximately 3–4 px at 0.85–0.95 opacity.

Exact values must be tuned in the visual QA pass.

### 4.5 Data-center symbols

Use a **12 px minimum visible diameter**, but recognize that the current markers are already about 14 px. The important improvements are:

- a 2–3 px white halo;
- a dark teal edge;
- top-pane ordering;
- an invisible interaction area of at least 44×44 CSS px for touch;
- a clear selected state with a second halo or ring;
- collision handling for near-identical coordinates.

At closer zoom, symbol area may be square-root-scaled by a clearly named measure, preferably backup-generation MW or documented electrical load. Cap the visible diameter at approximately 28–32 px. If size does not encode a data field, keep it constant rather than implying a quantity.

With relatively few projects, do not use broad clustering. For exact or near overlaps, show a small count badge at statewide zoom and fan/spiderfy the individual sites on activation. Every project must remain individually reachable.

### 4.6 Basemap and labels

Replace the busy default OpenStreetMap presentation with a low-saturation light basemap, subject to nonprofit licensing, traffic limits, privacy policy, uptime, and attribution review. A Positron-style map is a visual reference, not an automatic vendor decision.

Requirements:

- place names remain legible over thematic fills;
- labels render above context polygons where the provider/renderer supports it;
- roads and points of interest remain subordinate;
- state and county context is hairline-light;
- all required attribution remains visible and unobstructed;
- map functionality degrades gracefully if the basemap fails.

## 5. Legend redesign

Replace the fixed catalog with an **active-layer explanation**.

### Desktop

- Lower-left compact card.
- Collapsible without hiding the control shell.
- One section per visible thematic layer.
- Ordered by visual stack: analytical surface, data centers, infrastructure/context.
- Exact map swatches, including dash and hatch.
- Numeric endpoints, units, period, and missing-data treatment.
- Source, vintage, and full caveat behind a clearly labeled information disclosure.

### Mobile

- A “Legend” button opens a bottom sheet.
- The legend never competes with the detail sheet.
- Opening one sheet closes or minimizes the other.

### Required behaviors

- Every visible thematic layer has exactly one legend entry.
- No inactive layer appears.
- Legend content updates immediately after a layer or guided-view change.
- Alternative representations of one measure do not create duplicate entries.
- Map, legend, controls, detail panel, zoom buttons, and attribution never overlap.

## 6. Data-center interaction and information hierarchy

### 6.1 Hover and focus

Use a compact tooltip:

- project name;
- city;
- project status;
- backup generation MW;
- one view-specific fact.

The same summary must be available on keyboard focus and tap. Hover cannot be the only route to information.

### 6.2 Click/tap details

Replace the floating popup with:

- a 340–400 px docked right-side drawer on desktop;
- a dismissible bottom sheet on mobile.

The selected marker must remain visible. Opening the drawer must not recenter the marker beneath it. Support close button, Escape, and map click. Move focus into the drawer on open and return it to the originating marker on close.

Every drawer begins with:

- project name;
- status;
- owner;
- city and county;
- expected completion;
- CEC project and docket sources.

Then show a short view-specific summary. Put every remaining published field under **All project details**.

### 6.3 View-specific project fields

| View | Summary fields |
|---|---|
| **Overview** | Backup generation MW; total generators; backup fuel; point of interconnection; retail service provider |
| **Grid & reliability** | Point of interconnection; grid interconnection; dedicated facilities; documented grid upgrades; retail service provider; LRA match |
| **Equity & resilience** | Backup generation MW; total and load-serving generators; fuel; expected testing hours/year; annual fuel use; diesel PM percentile/top-quintile status; PSPS value, period, and coverage status |
| **Utility & upgrade evidence** | Retail service provider; mapped IOU territory; point of interconnection; grid interconnection; dedicated facilities; documented grid upgrades; ability to export/participate |

For fields central to the analytical question, show **Not documented** instead of silently omitting a blank. This is especially important for dedicated facilities, grid upgrades, generator details, and utility.

The Utility & upgrade evidence drawer must state:

> Project records can document dedicated facilities or broader grid work, but this map does not determine final utility cost allocation or rate treatment.

### 6.4 Accessible project list

Add a searchable, filterable data-center list below or beside the map:

- selecting a list row selects the same marker;
- selecting a marker selects the same row;
- every mapped project and published field is reachable without navigating the visual map;
- the list supplies the semantic alternative for screen-reader and keyboard users.

## 7. Design system

Use CSS custom properties and reusable components rather than adding more inline styles.

### 7.1 Core tokens

| Token role | Starting value |
|---|---|
| Ink | `#17212B` |
| Secondary text | `#52606D` |
| Surface | `#FFFFFF` |
| Muted surface | `#F4F6F8` |
| Border | `#CCD5DC` |
| Focus ring | `#006FC9`, 3 px |
| Data center | `#007C78` |
| TPP upgrade | `#B45309` |
| Existing transmission | `#526779` |
| LRA boundary | `#6D4AA5` |
| Missing/unreported | neutral gray pattern or blank |

These are starting tokens, not final approved colors. Freeze them only after contrast, grayscale, and color-vision testing.

### 7.2 Type and spacing

- Font stack: `system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`
- Base UI text: 16 px
- Compact control labels: 14 px
- Source/method metadata: no smaller than 12 px
- Spacing scale: 4, 8, 12, 16, 24, 32 px
- Card radius: 8 px
- Border: 1 px
- Shadow: restrained and used only to separate floating surfaces
- Sentence case throughout
- Left-align explanatory text
- Avoid decorative gradients except quantitative scales

This follows the design-token approach used by the U.S. Web Design System and the map-specific palette logic of ColorBrewer: ordered values use ordered lightness, while nominal topics use distinct hues and redundant shapes or patterns.

## 8. State, reset, and sharing

Represent these in the URL:

- active guided view;
- customized layer choices;
- center and zoom;
- selected data center;
- optional active-layer opacity.

Actions:

- **Reset view:** restore the active view's layer/style defaults without changing map extent.
- **Reset map:** restore Overview and statewide extent.
- **Copy link:** copy a reproducible URL and show a brief confirmation.
- Browser Back/Forward must restore meaningful view and selected-project states.

Only expose opacity controls when two active surfaces compete. Put the control beside the affected legend entry; do not create a global styling panel.

## 9. Accessibility requirements

Target WCAG 2.2 AA as the minimum.

- Restore browser and pinch zoom; remove the `user-scalable=no` restriction.
- Set page language and a meaningful document title.
- Give the map an accessible name and appropriate landmark.
- Add **Skip map** and **Skip to project list** links.
- Make tabs, view cards, checkboxes, legend controls, markers, and drawer operable by keyboard.
- Support Enter/Space to activate and Escape to close.
- Use visible focus rings that are never hidden by fixed panels.
- Give controls and map-feature interactions at least 44×44 px touch targets where practical; never fall below the WCAG 2.2 24×24 px minimum without the spacing exception.
- Maintain at least 4.5:1 contrast for normal text and 3:1 for meaningful non-text controls and boundaries.
- Do not convey meaning through color alone.
- Announce view and layer changes to assistive technology.
- Prevent keyboard traps in the map, control panel, legend, and drawer.
- Support 200% and 400% browser zoom.
- Respect `prefers-reduced-motion`.
- Ensure every hover behavior has a focus, click, and touch equivalent.
- Provide explicit missing-data text.

## 10. Performance and architecture

### 10.1 Immediate 80/20 improvements

- Do not render full substations and transmission in the default view.
- Use Canvas for dense infrastructure where compatible.
- Ship only properties required for styling, filtering, tooltips, or details.
- Store diesel tract geometry once and switch its style/filter rather than embedding it twice.
- Lazy-load inactive context layers on first activation.
- Serve production assets with Brotli or gzip.
- Consolidate repeated CSS.
- Remove unused Bootstrap, Font Awesome, jQuery, or marker dependencies only after verifying the final components do not use them.
- Cache immutable versioned data files.

### 10.2 Escalation path

First profile the simplified/lazy-loaded GeoJSON build. Move the largest statewide layers to vector tiles or PMTiles only if the first pass misses the performance budget. Do not take on a full renderer migration merely for architectural neatness.

Suggested budgets:

- compressed initial application shell below 1 MB;
- usable map within 3 seconds on a mid-range phone over simulated 4G;
- visible response to view and layer changes within 200 ms;
- no sustained main-thread block over 200 ms;
- smooth ordinary pan and zoom, targeting 45–60 fps.

## 11. Implementation sequence

### Phase 1 — freeze the experience contract

**Value:** very high  
**Effort:** low

1. Approve the four guided views and layer matrix.
2. Approve the visual grammar and semantic tokens.
3. Approve the data-center field matrix.
4. Freeze PSPS label, definition, range, bins, and missing-data wording.
5. Decide the production basemap only after licensing and attribution review.
6. Write configuration objects for views, layers, legends, fields, and styles so the UI and map cannot drift apart.

**Exit criterion:** one configuration specification describes every default view, active layer, legend entry, project field, and limitation.

### Phase 2 — fix the first impression

**Value:** very high  
**Effort:** moderate

1. Make Overview the default.
2. Remove general substations and full transmission from the default.
3. Lower existing-transmission weight and opacity.
4. Add semantic zoom and TPP-endpoint emphasis.
5. Add data-center halo, selected state, touch target, and overlap handling.
6. Apply the low-saturation basemap.

**Exit criterion:** at statewide extent, every data center and TPP upgrade is findable, place labels remain readable, and existing infrastructure never outranks the analytical evidence.

### Phase 3 — build guided views and DIY controls

**Value:** very high  
**Effort:** moderate

1. Build the accessible two-tab control.
2. Implement the four view presets.
3. Retain complete grouped layer controls in Build your own.
4. Add customized-state labeling and reset actions.
5. Preserve map extent on view changes.
6. Add URL state and Copy link.

**Exit criterion:** a first-time user can enter any analytical view in one click, while an expert can still access every layer.

### Phase 4 — redesign the legend and dual equity view

**Value:** very high  
**Effort:** moderate

1. Build active-only legend cards from shared layer configuration.
2. Replace the PSPS gradient with exact class swatches and the 1–15 range.
3. Add the complete PSPS definition and limitations disclosure.
4. Change diesel to purple sequential fill.
5. Implement PSPS pattern density in the combined view.
6. Add exact missing/unreported symbols.
7. Add limited contextual opacity controls only if usability testing needs them.

**Exit criterion:** diesel and PSPS can be decoded independently when shown together, including in grayscale and common color-vision simulations.

### Phase 5 — replace popups with structured details

**Value:** very high  
**Effort:** moderate

1. Implement compact hover/focus tooltips.
2. Implement the responsive detail drawer/bottom sheet.
3. Render the correct view-specific fields.
4. Add **All project details**.
5. Preserve source links and explicit missing values.
6. Add the synchronized accessible project list.

**Exit criterion:** no information surface obscures the selected site or legend, and every project is fully usable without hover.

### Phase 6 — accessibility and responsive completion

**Value:** required  
**Effort:** moderate

1. Correct page title, language, viewport, landmarks, and skip links.
2. Complete keyboard behavior and focus management.
3. Add assistive-technology announcements.
4. Test desktop, tablet, mobile, browser zoom, reduced motion, and forced colors.
5. Confirm no controls overlap.

**Exit criterion:** WCAG 2.2 AA acceptance checks pass and the application remains usable at supported widths and zoom levels.

### Phase 7 — performance hardening

**Value:** high  
**Effort:** moderate, with optional higher-effort escalation

1. Prune properties and duplicate geometry.
2. Lazy-load inactive layers.
3. Use Canvas for dense vectors.
4. Measure cold/warm load, toggle latency, pan/zoom responsiveness, and memory.
5. Adopt vector tiles/PMTiles only if measured performance still misses the budget.

**Exit criterion:** the published build meets the agreed budgets on a mid-range mobile device and standard desktop browsers.

## 12. Browser and user-testing protocol

The local `file://` map was blocked by the available browser security policy during this planning audit, and there was no already-open map tab to inspect. The source and generated HTML were audited directly. Before implementation starts, make the current map available at an approved preview URL or explicitly open it in a browser tab that can be claimed for testing.

Run two browser passes:

### Baseline pass before implementation

Record:

- default first impression;
- layer-control and legend footprint;
- actual panel collisions;
- marker visibility and overlap;
- popup obstruction;
- diesel/PSPS replacement behavior;
- pan, zoom, toggle, and hover latency;
- desktop and narrow-mobile screenshots.

### Verification pass after each implementation phase

Test these saved states:

- Overview;
- every guided view;
- Build your own with no context layers;
- diesel and PSPS together;
- full infrastructure;
- one selected data center;
- nearby or overlapping data centers;
- missing PSPS record;
- missing diesel value;
- collapsed and expanded legend;
- loading and data-fetch failure.

Test at:

- 320, 375, 768, 1024, and 1440 px widths;
- Chrome, Safari, Firefox, and Edge;
- iOS Safari and Android Chrome;
- mouse, keyboard only, touch, VoiceOver, and NVDA;
- 200% and 400% zoom;
- reduced motion and forced colors;
- deuteranopia, protanopia, tritanopia, and grayscale;
- slow 4G with cold and warm cache.

Conduct a five-person unmoderated comprehension check. At least four of five participants should correctly identify, without coaching:

1. the highest diesel-PM burden;
2. the highest reported PSPS frequency;
3. whether a selected site is in an LRA;
4. which lines are proposed upgrades versus existing infrastructure;
5. where to find the complete project record and sources.

## 13. Acceptance criteria

### First impression

- Overview opens with data centers and TPP upgrades prominent.
- General substations are not shown statewide by default.
- Existing transmission does not visually outrank TPP or data centers.
- City/place labels remain legible.

### Guided views and DIY

- One action activates each documented view.
- Only one guided view is active at a time.
- View changes update layers, legend, and data-center summaries correctly.
- Center and zoom are preserved after initial view entry.
- Customized state is visible.
- Full infrastructure and every context layer remain available in Build your own.

### Equity comparison

- Diesel and PSPS are distinguishable simultaneously by hue and pattern, not blended color.
- PSPS shows exact bins and observed range 1–15.
- Diesel shows a 0–100 percentile scale and 80th-percentile threshold.
- Unreported/missing is distinguishable from zero.
- The map remains interpretable in grayscale and common color-vision simulations.

### Data centers

- Visible symbols are at least 12 px in diameter with a white halo.
- Interaction targets are at least 44×44 px where practical.
- Every overlapping project can be individually selected.
- Click, tap, Enter, and Space open the same detail content.
- The selected marker remains visible.
- View-specific fields match the approved matrix.
- Complete details and source links remain available.

### Legend and panels

- Every active thematic layer has exactly one matching entry.
- No inactive layer appears.
- Map swatches and class boundaries exactly match the rendered styles.
- Legend, control shell, drawer, zoom controls, and attribution do not overlap at 1280×720, 1440×900, or 390×844.

### Accessibility, state, and performance

- All essential actions work without hover.
- Keyboard focus is visible and never trapped or obscured.
- Browser zoom and pinch zoom work.
- A copied URL reconstructs view, layers, extent, and selected site.
- Back/Forward restores meaningful map state.
- Initial load, view changes, and pan/zoom meet the agreed performance budgets.

## 14. Explicitly deferred work

Defer these unless testing demonstrates a need:

- nine-class bivariate choropleth;
- statewide clustering of a small project set;
- a fifth backup-generation view;
- extensive animation;
- user-configurable colors or line widths;
- full vector-tile/application-framework migration before profiling;
- clipping infrastructure to LRAs;
- opaque “smart” proximity filters without a visible distance rule.

These additions carry meaningful complexity but do not improve the core questions as much as the guided views, visual grammar, detail drawer, active legend, accessibility, and performance work above.

## 15. External design references

- [U.S. Web Design System design tokens](https://designsystem.digital.gov/design-tokens/) — disciplined color, spacing, and typography tokens.
- [U.S. Web Design System typography](https://designsystem.digital.gov/components/typography/) — readable type hierarchy and sizing.
- [ColorBrewer](https://colorbrewer2.org/) — map-appropriate sequential and colorblind-aware palettes.
- [Leaflet reference](https://leafletjs.com/reference) — panes, layer controls, and supported interaction primitives.
- [WCAG 2.2](https://www.w3.org/TR/WCAG22/) — accessibility requirements, including target size and focus behavior.
- [CARTO basemap documentation](https://docs.carto.com/carto-for-developers/key-concepts/carto-for-deck.gl/basemaps/carto-basemap) — a reference for low-saturation light basemap styles; provider selection still requires a separate licensing and operations decision.
