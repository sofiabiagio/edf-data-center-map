(function () {
  "use strict";

  const qs = (selector, root = document) => root.querySelector(selector);
  const qsa = (selector, root = document) => Array.from(root.querySelectorAll(selector));

  const MapApp = {
    init(bootstrap) {
      const { map, layers, markers, config } = bootstrap;
      if (!map || !layers || !config) return;

      const state = {
        mode: "guided",
        view: config.default_view,
        customized: false,
        selectedProject: null,
        selectedMarker: null,
        syncing: false,
        restoring: false,
      };
      const lazyState = new Map();

      const elements = {
        shell: qs("#map-app-control"),
        viewStatus: qs("#map-app-view-status"),
        guidedPanel: qs("#map-app-guided-panel"),
        diyPanel: qs("#map-app-diy-panel"),
        viewList: qs("#map-app-view-list"),
        layerList: qs("#map-app-layer-list"),
        legend: qs("#map-app-legend"),
        legendBody: qs("#map-app-legend-body"),
        drawer: qs("#map-app-drawer"),
        drawerEyebrow: qs("#map-app-drawer-eyebrow"),
        drawerTitle: qs("#map-app-drawer-title"),
        drawerMeta: qs("#map-app-drawer-meta"),
        drawerBody: qs("#map-app-drawer-body"),
        drawerClose: qs("#map-app-drawer-close"),
        projectButton: qs("#map-app-projects-button"),
        projectSearch: qs("#map-app-project-search"),
        projectList: qs("#map-app-project-list"),
        resetView: qs("#map-app-reset-view"),
        resetMap: qs("#map-app-reset-map"),
        methodology: qs("#map-app-methodology"),
        methodologyClose: qs("#map-app-methodology-close"),
        live: qs("#map-app-live"),
        toast: qs("#map-app-toast"),
      };

      map.getContainer().setAttribute("role", "region");
      document.body.classList.add("map-app-root");
      document.body.dataset.uiMounted = "true";
      map.getContainer().classList.add("map-app-map");
      map.getContainer().setAttribute(
        "aria-label",
        "Interactive map of proposed California data centers and grid, reliability, utility, pollution, and shutoff context"
      );
      map.getContainer().setAttribute("tabindex", "0");

      const markerById = new Map();
      markers.forEach((item) => {
        markerById.set(item.project.id, item);
        bindHoverPriority(item.marker);
        item.marker.on("click", (event) => {
          if (event.originalEvent && window.L) {
            window.L.DomEvent.stopPropagation(event.originalEvent);
          }
          activateProject(item.project, item.marker);
        });
        item.marker.on("add", () => makeMarkerAccessible(item));
        makeMarkerAccessible(item);
      });

      function announce(message) {
        elements.live.textContent = "";
        window.setTimeout(() => {
          elements.live.textContent = message;
        }, 20);
      }

      function makeMarkerAccessible(item) {
        const element = item.marker.getElement && item.marker.getElement();
        if (!element) return;
        element.setAttribute("tabindex", "0");
        element.setAttribute("role", "button");
        element.classList.add("map-app-data-center-marker");
        element.setAttribute(
          "aria-label",
          `Open details for ${item.project.name}`
        );
        if (element.dataset.mapAppKeyboardBound === "true") return;
        element.dataset.mapAppKeyboardBound = "true";
        if (state.selectedProject === item.project.id) {
          element.classList.add("map-app-marker--selected");
        }
        element.addEventListener("keydown", (event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            activateProject(item.project, item.marker);
          }
        });
      }

      function layerVisible(id) {
        return Boolean(layers[id] && map.hasLayer(layers[id]));
      }

      function escapeHtml(value) {
        return String(value == null ? "" : value)
          .replaceAll("&", "&amp;")
          .replaceAll("<", "&lt;")
          .replaceAll(">", "&gt;")
          .replaceAll('"', "&quot;")
          .replaceAll("'", "&#039;");
      }

      function classColor(value, classes) {
        const numeric = Number(value);
        const item = classes.find(
          (entry, index) =>
            numeric >= entry.minimum &&
            (numeric < entry.maximum ||
              (index === classes.length - 1 && numeric <= entry.maximum))
        );
        return item ? item.color : "#D7DCDA";
      }

      function lazyStyle(id, feature) {
        const lazy = config.layers[id].lazy;
        const properties = feature.properties || {};
        if (lazy.kind === "transmission") {
          return {
            color: lazy.color,
            weight: lazy.weight,
            opacity: lazy.opacity,
          };
        }
        if (lazy.kind === "diesel_percentile") {
          const value = properties.diesel_pm_percentile;
          if (value == null) {
            return {
              fillColor: "#D7DCDA",
              color: "#929D9A",
              weight: 0.25,
              fillOpacity: 0.24,
            };
          }
          return {
            fillColor: classColor(value, config.diesel_pm_scale.classes),
            color: "#6F6585",
            weight: 0.3,
            fillOpacity: 0.64,
          };
        }
        if (lazy.kind === "diesel_top_quintile") {
          return {
            fillColor: "#54278F",
            color: "#3F2B68",
            weight: 0.7,
            fillOpacity: 0.72,
          };
        }
        if (lazy.kind === "psps") {
          const value = Number(
            properties[config.psps_scale.field]
          );
          const index = Math.max(
            1,
            config.psps_scale.classes.findIndex(
              (entry) => value >= entry.minimum && value <= entry.maximum
            ) + 1
          );
          return {
            fillColor: `url(#psps-pattern-${index})`,
            color: "#049834",
            weight: 0.65,
            fillOpacity: 1,
          };
        }
        return {};
      }

      function bindLazyTooltip(feature, layer, lazy) {
        const rows = (lazy.tooltip || [])
          .map(({ field, label }) => {
            const value = feature.properties && feature.properties[field];
            if (value == null || String(value).trim() === "") return "";
            return `<div><strong>${escapeHtml(label)}</strong> ${escapeHtml(
              value
            )}</div>`;
          })
          .filter(Boolean)
          .join("");
        if (rows) layer.bindTooltip(rows, { sticky: false });
        bindHoverPriority(layer);
      }

      function bindHoverPriority(layer) {
        if (!layer || !layer.on) return;
        layer.on("mouseover", () => {
          if (layer.bringToFront) layer.bringToFront();
          const tooltip = layer.getTooltip && layer.getTooltip();
          if (tooltip && tooltip.bringToFront) tooltip.bringToFront();
        });
      }

      function loadLocalLayerScript(id, scriptUrl) {
        return new Promise((resolve, reject) => {
          const script = document.createElement("script");
          script.src = scriptUrl;
          script.async = true;
          script.onload = () => {
            const registry = window.__MAP_APP_LAYER_DATA__ || {};
            const data = registry[id];
            script.remove();
            if (!data) {
              reject(new Error(`Layer script did not register ${id}`));
              return;
            }
            delete registry[id];
            resolve(data);
          };
          script.onerror = () => {
            script.remove();
            reject(new Error(`Could not load ${scriptUrl}`));
          };
          document.head.appendChild(script);
        });
      }

      async function loadLazyData(id, lazy) {
        if (window.location.protocol === "file:" && lazy.script_url) {
          return loadLocalLayerScript(id, lazy.script_url);
        }
        try {
          const response = await fetch(lazy.url, { cache: "force-cache" });
          if (!response.ok) throw new Error(`HTTP ${response.status}`);
          return await response.json();
        } catch (error) {
          if (lazy.script_url) {
            return loadLocalLayerScript(id, lazy.script_url);
          }
          throw error;
        }
      }

      async function ensureLayerLoaded(id) {
        const lazy = config.layers[id] && config.layers[id].lazy;
        if (!lazy || lazyState.get(id) === "loaded") return;
        if (lazyState.get(id) === "loading") return;
        lazyState.set(id, "loading");
        showToast(`Loading ${config.layers[id].label}…`);
        try {
          const data = await loadLazyData(id, lazy);
          const options = {
            pane: lazy.pane,
            style: (feature) => lazyStyle(id, feature),
            onEachFeature: (feature, layer) =>
              bindLazyTooltip(feature, layer, lazy),
          };
          if (lazy.kind === "substations") {
            options.pointToLayer = (_feature, latlng) =>
              window.L.circleMarker(latlng, {
                pane: lazy.pane,
                radius: 2.5,
                color: lazy.color,
                weight: 1,
                fill: true,
                fillColor: lazy.color,
                fillOpacity: 0.62,
              });
          }
          if (lazy.filter_field) {
            options.filter = (feature) => {
              const value = Number(
                feature.properties && feature.properties[lazy.filter_field]
              );
              return (
                Number.isFinite(value) &&
                (lazy.filter_min == null || value >= lazy.filter_min) &&
                (lazy.filter_max == null || value <= lazy.filter_max)
              );
            };
          }
          window.L.geoJSON(data, options).addTo(layers[id]);
          lazyState.set(id, "loaded");
          showToast(`${config.layers[id].label} ready`);
        } catch (error) {
          console.error(`Could not load map layer ${id}`, error);
          lazyState.set(id, "error");
          setLayer(id, false);
          renderAll();
          showToast(`Could not load ${config.layers[id].label}`);
          announce(
            `${config.layers[id].label} could not be loaded. Other map controls remain available.`
          );
        }
      }

      function setLayer(id, visible) {
        const layer = layers[id];
        if (!layer) return;
        const present = map.hasLayer(layer);
        if (visible) {
          if (!present) map.addLayer(layer);
          ensureLayerLoaded(id);
        }
        if (!visible && present) map.removeLayer(layer);
      }

      function desiredLayersForView(viewId) {
        const view = config.views[viewId];
        const desired = new Set(view.layers);
        const zoom = map.getZoom();
        Object.entries(config.layers).forEach(([id, layerConfig]) => {
          if (!desired.has(id) || layerConfig.min_zoom == null) return;
          if (zoom < layerConfig.min_zoom) desired.delete(id);
        });
        return desired;
      }

      function reconcileView(
        viewId,
        { preserveExtent = true, pushHistory = false } = {}
      ) {
        const view = config.views[viewId];
        if (!view) return;
        const center = map.getCenter();
        const zoom = map.getZoom();
        const desired = desiredLayersForView(viewId);
        state.syncing = true;
        Object.keys(config.layers).forEach((id) => {
          setLayer(id, desired.has(id));
        });
        state.syncing = false;
        state.view = viewId;
        state.mode = "guided";
        state.customized = false;
        if (preserveExtent) map.setView(center, zoom, { animate: false });
        renderAll();
        syncUrl({ push: pushHistory });
        announce(`${view.label} view active.`);
      }

      function renderViews() {
        elements.viewList.replaceChildren();
        Object.entries(config.views).forEach(([id, view]) => {
          const button = document.createElement("button");
          button.type = "button";
          button.className = "map-app-view-card";
          button.dataset.view = id;
          button.setAttribute(
            "aria-pressed",
            String(state.mode === "guided" && state.view === id)
          );

          const title = document.createElement("span");
          title.className = "map-app-view-card__title";
          title.textContent = view.label;
          const question = document.createElement("span");
          question.className = "map-app-view-card__description";
          question.textContent = view.question;
          button.append(title, question);
          button.addEventListener("click", () =>
            reconcileView(id, { pushHistory: true })
          );
          elements.viewList.append(button);
        });
      }

      function createCheckbox(id, layerConfig) {
        const row = document.createElement("label");
        row.className = "map-app-layer-control";
        const input = document.createElement("input");
        input.type = "checkbox";
        input.className = "map-app-layer-control__input";
        input.dataset.layer = id;
        input.checked = layerVisible(id);
        input.setAttribute(
          "aria-label",
          `${layerVisible(id) ? "Hide" : "Show"} ${layerConfig.label}`
        );
        const swatch = document.createElement("span");
        swatch.className = `map-app-legend__swatch map-app-layer-swatch--${id}`;
        swatch.setAttribute("aria-hidden", "true");
        const text = document.createElement("span");
        text.className = "map-app-layer-control__label";
        text.textContent = layerConfig.label;
        row.append(input, swatch, text);
        input.addEventListener("change", () => {
          if (input.checked && layerConfig.family) {
            Object.entries(config.layers).forEach(([otherId, other]) => {
              if (otherId !== id && other.family === layerConfig.family) {
                setLayer(otherId, false);
              }
            });
          }
          setLayer(id, input.checked);
          state.customized = true;
          renderAll();
          syncUrl({ push: true });
        });
        return row;
      }

      function renderLayers() {
        elements.layerList.replaceChildren();
        config.layer_categories.forEach((category) => {
          const section = document.createElement("fieldset");
          section.className = "map-app-control-group";
          const legend = document.createElement("legend");
          legend.className = "map-app-control-group__title";
          legend.textContent = category.label;
          section.append(legend);
          category.layers.forEach((id) => {
            const layerConfig = config.layers[id];
            if (layerConfig) section.append(createCheckbox(id, layerConfig));
          });
          elements.layerList.append(section);
        });
      }

      function addLegendText(parent, text, className) {
        const node = document.createElement("div");
        node.className = className;
        node.textContent = text;
        parent.append(node);
      }

      function renderLegend() {
        elements.legendBody.replaceChildren();
        const visible = config.legend_order.filter(
          (id) => config.layers[id] && layerVisible(id)
        );
        const renderedGroups = new Set();
        const pspsPatternGaps = [12, 11, 9, 7, 5, 4];
        elements.legend.hidden = visible.length === 0;

        visible.forEach((id) => {
          const layerConfig = config.layers[id];
          const groupId = layerConfig.legend.group;
          if (groupId && renderedGroups.has(groupId)) return;

          const section = document.createElement("section");
          section.className = "map-app-legend__section";
          section.dataset.layer = groupId || id;

          const heading = document.createElement("h3");
          heading.className = "map-app-legend__section-title";
          heading.textContent = layerConfig.legend.title;
          section.append(heading);

          if (layerConfig.legend.summary) {
            const summary = document.createElement("p");
            summary.className = "map-app-legend__summary";
            summary.textContent = layerConfig.legend.summary;
            section.append(summary);
          }

          if (groupId) {
            const groupedLayers = visible.filter(
              (candidateId) =>
                config.layers[candidateId].legend.group === groupId
            );
            const classes = document.createElement("div");
            classes.className = "map-app-legend__items";
            groupedLayers.forEach((groupedId) => {
              const groupedConfig = config.layers[groupedId];
              const row = document.createElement("div");
              row.className = "map-app-legend__item";
              const swatch = document.createElement("span");
              swatch.className =
                `map-app-legend__swatch map-app-layer-swatch--${groupedId}`;
              const label = document.createElement("span");
              label.textContent =
                groupedConfig.legend.label || groupedConfig.label;
              row.append(swatch, label);
              classes.append(row);
            });
            section.append(classes);
            renderedGroups.add(groupId);
          } else if (layerConfig.legend.type === "classes") {
            const classes = document.createElement("div");
            classes.className = "map-app-legend__items";
            layerConfig.legend.items.forEach((item, index) => {
              const row = document.createElement("div");
              row.className = "map-app-legend__item";
              const swatch = document.createElement("span");
              swatch.className = "map-app-legend__swatch";
              if (item.color) swatch.style.backgroundColor = item.color;
              if (item.pattern) {
                swatch.classList.add("map-app-legend__swatch--psps");
                swatch.style.setProperty("--pattern-color", item.pattern);
                swatch.style.setProperty(
                  "--pattern-gap",
                  `${pspsPatternGaps[index] || 4}px`
                );
              }
              if (item.line) {
                swatch.classList.add("map-app-legend__swatch--line");
                swatch.style.borderTopColor = item.color;
                if (item.dashed) swatch.style.borderTopStyle = "dashed";
                if (item.line_case) {
                  swatch.classList.add(
                    `map-app-legend__swatch--${item.line_case}`
                  );
                }
              }
              if (item.symbol_kind) {
                swatch.classList.add(
                  "map-app-legend__swatch--symbol",
                  `map-app-legend__swatch--${item.symbol_kind}`
                );
              }
              const label = document.createElement("span");
              label.textContent = item.label;
              row.append(swatch, label);
              classes.append(row);
            });
            section.append(classes);
          } else if (layerConfig.legend.type === "gradient") {
            const ramp = document.createElement("div");
            ramp.className = "map-app-legend__scale";
            ramp.style.background = `linear-gradient(90deg, ${layerConfig.legend.colors.join(",")})`;
            const ticks = document.createElement("div");
            ticks.className = "map-app-legend__ticks";
            layerConfig.legend.ticks.forEach((tick) => {
              const value = document.createElement("span");
              value.textContent = tick;
              ticks.append(value);
            });
            section.append(ramp, ticks);
          } else {
            const row = document.createElement("div");
            row.className = "map-app-legend__item";
            const swatch = document.createElement("span");
            swatch.className = `map-app-legend__swatch map-app-layer-swatch--${id}`;
            const label = document.createElement("span");
            label.textContent = layerConfig.legend.label || layerConfig.label;
            row.append(swatch, label);
            section.append(row);
          }

          if (layerConfig.legend.range) {
            addLegendText(
              section,
              layerConfig.legend.range,
              "map-app-legend__value"
            );
          }
          if (layerConfig.legend.missing) {
            const missingRow = document.createElement("div");
            missingRow.className =
              "map-app-legend__item map-app-legend__item--missing";
            const missingSwatch = document.createElement("span");
            missingSwatch.className =
              "map-app-legend__swatch map-app-legend__swatch--missing";
            const missingLabel = document.createElement("span");
            missingLabel.className = "map-app-value--missing";
            missingLabel.textContent = layerConfig.legend.missing;
            missingRow.append(missingSwatch, missingLabel);
            section.append(missingRow);
          }
          if (layerConfig.legend.note) {
            if (layerConfig.legend.note_display === "visible") {
              addLegendText(
                section,
                layerConfig.legend.note,
                "map-app-legend__note"
              );
            } else {
              const details = document.createElement("details");
              details.className = "map-app-legend__details";
              const summary = document.createElement("summary");
              summary.textContent = "Definition & caveats";
              const note = document.createElement("p");
              note.textContent = layerConfig.legend.note;
              details.append(summary, note);
              section.append(details);
            }
          }
          elements.legendBody.append(section);
        });
      }

      function renderViewStatus() {
        const view = config.views[state.view];
        elements.viewStatus.textContent =
          state.mode === "guided"
            ? `${view.label}${state.customized ? " · customized" : ""}`
            : `Build your own${state.customized ? " · customized" : ""}`;
        qsa("[data-view]", elements.viewList).forEach((button) => {
          button.setAttribute(
            "aria-pressed",
            String(state.mode === "guided" && button.dataset.view === state.view)
          );
        });
      }

      function renderAll() {
        renderViewStatus();
        renderLayers();
        renderLegend();
        qsa("[data-map-tab]").forEach((tab) => {
          const selected = tab.dataset.mapTab === state.mode;
          tab.setAttribute("aria-selected", String(selected));
          tab.tabIndex = selected ? 0 : -1;
        });
        elements.guidedPanel.hidden = state.mode !== "guided";
        elements.diyPanel.hidden = state.mode !== "diy";
      }

      function fieldValue(project, field) {
        const value = project.fields[field];
        if (value === null || value === undefined || String(value).trim() === "") {
          if (field === "map_psps_frequency") {
            return "No reported-impact record; not treated as zero";
          }
          if (field === "map_diesel_pm_percentile") {
            return "No diesel PM value";
          }
          return "Not documented";
        }
        return String(value);
      }

      function detailRow(label, value) {
        const row = document.createElement("div");
        row.className = "map-app-detail-list__row";
        const term = document.createElement("dt");
        term.textContent = label;
        const description = document.createElement("dd");
        description.textContent = value;
        row.append(term, description);
        return row;
      }

      function renderProjectDetail(project) {
        elements.drawerEyebrow.textContent =
          config.views[state.view].label;
        elements.drawerTitle.textContent = project.name;
        elements.drawerMeta.textContent = [
          fieldValue(project, "PROJECT_STATUS"),
          [fieldValue(project, "CITY"), fieldValue(project, "COUNTY")]
            .filter((value) => value !== "Not documented")
            .join(", "),
        ]
          .filter(Boolean)
          .join(" · ");
        elements.drawerBody.replaceChildren();

        const view = config.views[state.view];
        const intro = document.createElement("p");
        intro.className = "map-app-detail-summary";
        intro.textContent = view.detail_intro;
        elements.drawerBody.append(intro);

        const contextHeading = document.createElement("h3");
        contextHeading.className = "map-app-detail-heading";
        contextHeading.textContent = "Relevant project evidence";
        elements.drawerBody.append(contextHeading);

        const summary = document.createElement("dl");
        summary.className = "map-app-detail-list";
        Array.from(
          new Set(config.identity_fields.concat(view.detail_fields))
        ).forEach((field) => {
          const label = config.field_labels[field] || field;
          summary.append(detailRow(label, fieldValue(project, field)));
        });
        elements.drawerBody.append(summary);

        const sources = document.createElement("div");
        sources.className = "map-app-detail-section";
        if (project.sources.length) {
          const sourcesHeading = document.createElement("h3");
          sourcesHeading.className = "map-app-detail-heading";
          sourcesHeading.textContent = "Source documents";
          sources.append(sourcesHeading);
        }
        project.sources.forEach((source) => {
          const link = document.createElement("a");
          link.href = source.url;
          link.target = "_blank";
          link.rel = "noopener";
          link.textContent = source.label;
          sources.append(link);
        });
        if (project.sources.length) elements.drawerBody.append(sources);

        const details = document.createElement("details");
        details.className = "map-app-disclosure";
        const detailsSummary = document.createElement("summary");
        detailsSummary.textContent = "View complete project record";
        const all = document.createElement("dl");
        all.className = "map-app-detail-list";
        config.all_detail_fields.forEach((field) => {
          all.append(
            detailRow(
              config.field_labels[field] || field,
              fieldValue(project, field)
            )
          );
        });
        details.append(detailsSummary, all);
        elements.drawerBody.append(details);
      }

      function clearSelectedMarker() {
        if (!state.selectedMarker) return;
        if (state.selectedMarker.setStyle) {
          state.selectedMarker.setStyle({
            color: config.tokens.data_center_edge,
            weight: 2,
            fillColor: config.tokens.data_center,
            fillOpacity: 0.96,
          });
        }
        const element =
          state.selectedMarker.getElement && state.selectedMarker.getElement();
        if (element) element.classList.remove("map-app-marker--selected");
      }

      function activateProject(project, marker) {
        if (map.getZoom() < 12) {
          map.setView(marker.getLatLng(), 13, {
            animate: !window.matchMedia("(prefers-reduced-motion: reduce)").matches,
          });
        }
        openProject(project, marker);
      }

      function openProject(
        project,
        marker,
        { focusDrawer = true, pushHistory = true } = {}
      ) {
        clearSelectedMarker();
        state.selectedProject = project.id;
        state.selectedMarker = marker;
        if (marker.setStyle) {
          marker.setStyle({
            color: config.tokens.ink,
            weight: 4,
            fillColor: config.tokens.data_center,
            fillOpacity: 1,
          });
        }
        if (marker.bringToFront) marker.bringToFront();
        const markerElement = marker.getElement && marker.getElement();
        if (markerElement) markerElement.classList.add("map-app-marker--selected");
        renderProjectDetail(project);
        elements.drawer.hidden = false;
        elements.drawer.dataset.open = "true";
        document.body.classList.add("map-app-drawer-open");
        map.getContainer().classList.add("is-detail-open");
        if (marker.getLatLng) {
          map.panInside(marker.getLatLng(), {
            paddingTopLeft: [24, 110],
            paddingBottomRight: [430, 64],
            animate: false,
          });
        }
        if (focusDrawer) elements.drawerClose.focus();
        syncProjectListSelection();
        syncUrl({ push: pushHistory });
        announce(`Project details opened for ${project.name}.`);
      }

      function closeDrawer(
        { restoreFocus = true, pushHistory = true } = {}
      ) {
        const markerElement =
          state.selectedMarker &&
          state.selectedMarker.getElement &&
          state.selectedMarker.getElement();
        clearSelectedMarker();
        state.selectedMarker = null;
        state.selectedProject = null;
        elements.drawer.hidden = true;
        elements.drawer.dataset.open = "false";
        document.body.classList.remove("map-app-drawer-open");
        map.getContainer().classList.remove("is-detail-open");
        syncProjectListSelection();
        syncUrl({ push: pushHistory });
        if (restoreFocus && markerElement) markerElement.focus();
      }

      function closeMobileSheets(except) {
        if (except !== "controls") elements.shell.dataset.open = "false";
        if (except !== "legend") elements.legend.dataset.open = "false";
        if (except !== "drawer" && !elements.drawer.hidden) {
          closeDrawer({ restoreFocus: false });
        }
      }

      function renderProjectList(filter = "") {
        const normalized = filter.trim().toLowerCase();
        elements.projectList.replaceChildren();
        markers
          .map((item) => item.project)
          .filter((project) => {
            const haystack = [
              project.name,
              fieldValue(project, "CITY"),
              fieldValue(project, "COUNTY"),
              fieldValue(project, "PROJECT_STATUS"),
            ]
              .join(" ")
              .toLowerCase();
            return !normalized || haystack.includes(normalized);
          })
          .sort((a, b) => a.name.localeCompare(b.name))
          .forEach((project) => {
            const button = document.createElement("button");
            button.type = "button";
            button.className = "map-app-project-row";
            button.dataset.project = project.id;
            const title = document.createElement("strong");
            title.className = "map-app-project-row__name";
            title.textContent = project.name;
            const meta = document.createElement("span");
            meta.className = "map-app-project-row__meta";
            meta.textContent = [
              fieldValue(project, "CITY"),
              fieldValue(project, "PROJECT_STATUS"),
            ]
              .filter((value) => value !== "Not documented")
              .join(" · ");
            button.append(title, meta);
            button.addEventListener("click", () => {
              const item = markerById.get(project.id);
              if (!layerVisible("data_centers")) setLayer("data_centers", true);
              map.setView(item.marker.getLatLng(), Math.max(map.getZoom(), 16), {
                animate: !window.matchMedia("(prefers-reduced-motion: reduce)").matches,
              });
              openProject(project, item.marker);
            });
            elements.projectList.append(button);
          });
        syncProjectListSelection();
      }

      function syncProjectListSelection() {
        qsa("[data-project]", elements.projectList).forEach((button) => {
          const selected = button.dataset.project === state.selectedProject;
          button.classList.toggle("is-selected", selected);
          button.setAttribute("aria-selected", selected ? "true" : "false");
        });
      }

      function setTab(mode) {
        if (!["guided", "diy"].includes(mode)) return;
        state.mode = mode;
        renderAll();
        syncUrl();
        const activePanel = mode === "guided" ? elements.guidedPanel : elements.diyPanel;
        const firstControl = qs("button, input", activePanel);
        if (firstControl) firstControl.focus();
      }

      function activeLayerIds() {
        return Object.keys(config.layers).filter(layerVisible);
      }

      function syncUrl({ push = false } = {}) {
        if (state.restoring) return;
        const url = new URL(window.location.href);
        url.searchParams.set("view", state.view);
        if (state.mode === "diy" || state.customized) {
          url.searchParams.set("layers", activeLayerIds().join(","));
        } else {
          url.searchParams.delete("layers");
        }
        const center = map.getCenter();
        url.searchParams.set("lat", center.lat.toFixed(4));
        url.searchParams.set("lng", center.lng.toFixed(4));
        url.searchParams.set("z", String(map.getZoom()));
        if (state.selectedProject) {
          url.searchParams.set("project", state.selectedProject);
        } else {
          url.searchParams.delete("project");
        }
        history[push ? "pushState" : "replaceState"](
          {
            view: state.view,
            mode: state.mode,
            layers: activeLayerIds(),
            selectedProject: state.selectedProject,
          },
          "",
          url
        );
      }

      function restoreUrlState() {
        state.restoring = true;
        const params = new URLSearchParams(window.location.search);
        const view = params.get("view");
        if (view && config.views[view]) state.view = view;
        const lat = Number(params.get("lat"));
        const lng = Number(params.get("lng"));
        const zoom = Number(params.get("z"));
        if (
          Number.isFinite(lat) &&
          Number.isFinite(lng) &&
          Number.isFinite(zoom) &&
          lat >= 32 &&
          lat <= 43 &&
          lng >= -125 &&
          lng <= -113 &&
          zoom >= 5 &&
          zoom <= 18
        ) {
          map.setView([lat, lng], zoom, { animate: false });
        }
        const layerParam = params.get("layers");
        if (params.has("layers")) {
          const requested = new Set(
            layerParam.split(",").filter((id) => config.layers[id])
          );
          state.syncing = true;
          Object.keys(config.layers).forEach((id) => {
            setLayer(id, requested.has(id));
          });
          state.syncing = false;
          state.mode = "diy";
          state.customized = true;
        } else {
          reconcileView(state.view, { preserveExtent: true });
        }
        const projectId = params.get("project");
        if (projectId && markerById.has(projectId)) {
          const item = markerById.get(projectId);
          openProject(item.project, item.marker, {
            focusDrawer: false,
            pushHistory: false,
          });
        }
        state.restoring = false;
        syncUrl();
      }

      function showToast(message) {
        elements.toast.textContent = message;
        elements.toast.hidden = false;
        elements.toast.dataset.visible = "true";
        window.clearTimeout(showToast.timer);
        showToast.timer = window.setTimeout(() => {
          elements.toast.dataset.visible = "false";
          elements.toast.hidden = true;
        }, 2200);
      }

      qsa("[data-map-tab]").forEach((tab) => {
        tab.addEventListener("click", () => setTab(tab.dataset.mapTab));
        tab.addEventListener("keydown", (event) => {
          if (!["ArrowLeft", "ArrowRight"].includes(event.key)) return;
          event.preventDefault();
          setTab(tab.dataset.mapTab === "guided" ? "diy" : "guided");
        });
      });

      elements.resetView.addEventListener("click", () =>
        reconcileView(state.view)
      );
      elements.resetMap.addEventListener("click", () => {
        state.view = config.default_view;
        map.setView(config.initial_view.center, config.initial_view.zoom, {
          animate: false,
        });
        closeDrawer({ restoreFocus: false });
        reconcileView(config.default_view);
      });
      elements.drawerClose.addEventListener("click", () => closeDrawer());
      elements.projectButton.addEventListener("click", () => {
        elements.drawerEyebrow.textContent = "Project index";
        elements.drawerTitle.textContent = "Browse data centers";
        elements.drawerMeta.textContent = `${markers.length} mapped projects`;
        elements.drawerBody.replaceChildren(
          elements.projectSearch,
          elements.projectList
        );
        elements.projectSearch.hidden = false;
        elements.projectList.hidden = false;
        renderProjectList();
        elements.drawer.hidden = false;
        elements.drawer.dataset.open = "true";
        document.body.classList.add("map-app-drawer-open");
        map.getContainer().classList.add("is-detail-open");
        elements.projectSearch.focus();
      });
      elements.projectSearch.addEventListener("input", () =>
        renderProjectList(elements.projectSearch.value)
      );
      qsa("[data-methodology-open]").forEach((button) => {
        button.addEventListener("click", () => {
          if (elements.methodology.showModal) elements.methodology.showModal();
          else elements.methodology.setAttribute("open", "");
        });
      });
      elements.methodologyClose.addEventListener("click", () =>
        elements.methodology.close()
      );
      qsa("[data-mobile-panel]").forEach((button) => {
        button.addEventListener("click", () => {
          const panel = button.dataset.mobilePanel;
          if (panel === "controls") {
            const opening = elements.shell.dataset.open !== "true";
            closeMobileSheets(opening ? "controls" : null);
            elements.shell.dataset.open = String(opening);
          } else if (panel === "legend") {
            const opening = elements.legend.dataset.open !== "true";
            closeMobileSheets(opening ? "legend" : null);
            elements.legend.dataset.open = String(opening);
          } else {
            closeMobileSheets("drawer");
            elements.projectButton.click();
          }
        });
      });
      const collapseControl = qs("[data-map-collapse]");
      collapseControl.addEventListener("click", () => {
        const collapsed = elements.shell.dataset.collapsed === "true";
        elements.shell.dataset.collapsed = String(!collapsed);
        collapseControl.setAttribute("aria-expanded", String(collapsed));
        collapseControl.textContent = collapsed ? "−" : "+";
      });
      const collapseLegend = qs("[data-legend-collapse]");
      collapseLegend.addEventListener("click", () => {
        const collapsed = elements.legend.dataset.collapsed === "true";
        elements.legend.dataset.collapsed = String(!collapsed);
        collapseLegend.setAttribute("aria-expanded", String(collapsed));
        collapseLegend.textContent = collapsed ? "−" : "+";
      });
      document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && !elements.drawer.hidden) closeDrawer();
      });
      window.addEventListener("popstate", () => {
        state.restoring = true;
        if (!elements.drawer.hidden) {
          closeDrawer({ restoreFocus: false, pushHistory: false });
        }
        restoreUrlState();
        renderAll();
      });

      map.on("zoomend", () => {
        if (state.mode === "guided") {
          const desired = desiredLayersForView(state.view);
          state.syncing = true;
          Object.entries(config.layers).forEach(([id, layerConfig]) => {
            if (
              config.views[state.view].layers.includes(id) &&
              layerConfig.min_zoom != null
            ) {
              setLayer(id, desired.has(id));
            }
          });
          state.syncing = false;
          renderAll();
        }
        syncUrl();
      });
      map.on("moveend", syncUrl);
      map.on("click", (event) => {
        const target = event.originalEvent && event.originalEvent.target;
        if (target && target.closest && target.closest(".map-app-data-center-marker")) {
          return;
        }
        if (!elements.drawer.hidden && state.selectedProject) closeDrawer();
      });
      map.on("overlayadd overlayremove", () => {
        if (state.syncing) return;
        renderAll();
      });

      renderViews();
      renderProjectList();
      restoreUrlState();
      renderAll();

      window.__MAP_APP__ = {
        getState: () => ({
          mode: state.mode,
          view: state.view,
          customized: state.customized,
          visibleLayers: activeLayerIds(),
          selectedProject: state.selectedProject,
          center: map.getCenter(),
          zoom: map.getZoom(),
        }),
        getConfig: () => config,
        applyView: (viewId) => reconcileView(viewId),
      };
    },
  };

  window.MapApp = MapApp;
})();
