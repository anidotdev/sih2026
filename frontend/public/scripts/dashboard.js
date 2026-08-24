import {
  loadHealth,
  loadStates,
  loadFires,
} from "./dashboard/api.js";

import {
  loadIndustrialForState,
} from "./dashboard/industrial.js";

import {
  initializeTheme,
} from "./dashboard/theme.js";

import {
  renderStats,
} from "./dashboard/stats.js";

import {
  renderAlerts,
} from "./dashboard/alerts.js";

import {
  renderTable,
} from "./dashboard/table.js";

import {
  initializeMap,
  updateFireSource,
  updateIndustrialSource,
} from "./dashboard/map.js";

import {
  state,
} from "./dashboard/state.js";

import {
  createClusterSelector,
  setupDetailClose,
} from "./dashboard/cluster-detail.js";

import {
  formatLabel,
} from "./dashboard/utils.js";


/* ============================================================
   Theme
   ============================================================ */

initializeTheme();

setupDetailClose();


/* ============================================================
   Cluster selector
   ============================================================ */

const selectCluster =
  createClusterSelector(
    () => state.clusters,
    () => state.map
  );


/* ============================================================
   State selector
   ============================================================ */

function setupStateSelector() {
  const selector =
    document.querySelector(
      "#state-select"
    );

  if (!selector) {
    return;
  }

  selector.addEventListener(
    "change",
    async (event) => {
      const selectedState =
        event.target.value;

      if (!selectedState) {
        return;
      }

      await selectState(
        selectedState
      );
    }
  );
}


/* ============================================================
   Populate states
   ============================================================ */

async function populateStates() {
  const selector =
    document.querySelector(
      "#state-select"
    );

  if (!selector) {
    return;
  }

  try {
    const data =
      await loadStates();

    state.states =
      Array.isArray(data.states)
        ? data.states
        : [];

    if (!state.states.length) {
      throw new Error(
        "Backend returned no states."
      );
    }

    selector.innerHTML =
      state.states
        .map(
          (item) => `
            <option value="${escapeHtml(item.name)}">
              ${escapeHtml(item.name)}
            </option>
          `
        )
        .join("");


    /*
     * Prefer Haryana as the initial state.
     */
    const haryana =
      state.states.find(
        (item) =>
          item.name ===
          "Haryana"
      );


    if (haryana) {
      state.selectedState =
        "Haryana";

      selector.value =
        "Haryana";

    } else {

      state.selectedState =
        state.states[0].name;

      selector.value =
        state.selectedState;
    }


    /*
     * IMPORTANT:
     * The HTML starts the selector as disabled while
     * states are loading. Re-enable it after loading.
     */
    selector.disabled =
      false;


    console.log(
      `Loaded ${state.states.length} states`
    );

  } catch (error) {

    console.error(
      "Failed to load states:",
      error
    );


    /*
     * Fallback to Haryana.
     */
    state.states = [
      {
        name: "Haryana",
      },
    ];

    state.selectedState =
      "Haryana";


    selector.innerHTML = `
      <option value="Haryana">
        Haryana
      </option>
    `;


    /*
     * IMPORTANT:
     * Even if /states fails, the selector must still
     * be usable.
     */
    selector.disabled =
      false;


    const context =
      document.querySelector(
        "#map-context"
      );

    if (context) {
      context.textContent =
        "Haryana";
    }
  }
}


/* ============================================================
   State selection
   ============================================================ */

async function selectState(
  stateName
) {
  if (!stateName) {
    return;
  }


  state.selectedState =
    stateName;


  const selector =
    document.querySelector(
      "#state-select"
    );


  if (selector) {
    selector.value =
      stateName;
  }


  const context =
    document.querySelector(
      "#map-context"
    );


  if (context) {
    context.textContent =
      stateName;
  }


  const industrialCount =
    document.querySelector(
      "#industrial-count"
    );


  if (industrialCount) {
    industrialCount.textContent =
      "Loading...";
  }


  const alerts =
    document.querySelector(
      "#alerts"
    );


  if (alerts) {
    alerts.innerHTML = `
      <div class="empty">
        Loading alerts...
      </div>
    `;
  }


  try {

    /*
     * Fetch both datasets concurrently.
     */
    const [
      fireData,
      industrialData,
    ] = await Promise.all([
      loadFires(
        stateName
      ),

      loadIndustrialForState(
        stateName
      ),
    ]);


    /*
     * Store fire clusters.
     */
    state.clusters =
      Array.isArray(
        fireData.clusters
      )
        ? fireData.clusters
        : [];


    /*
     * Store industrial data if the helper didn't already.
     */
    if (industrialData) {
      state.industrialData =
        industrialData;
    }


    /*
     * Render dashboard.
     */
    renderStats(
      state.clusters
    );


    renderAlerts(
      state.clusters,
      selectCluster
    );


    renderTable(
      state.clusters,
      selectCluster
    );


    /*
     * Update map sources.
     */
    updateIndustrialSource();

    updateFireSource();


    /*
     * Update industrial feature count.
     */
    if (industrialCount) {

      const count =
        state.industrialData
          ?.features
          ?.length || 0;

      industrialCount.textContent =
        `${count} industrial features`;
    }


    /*
     * Center on selected state's bbox.
     */
    if (
      state.map &&
      fireData &&
      fireData.bbox
    ) {
      centerMapOnState(
        fireData.bbox
      );
    }

  } catch (error) {

    console.error(
      `Failed loading ${stateName}:`,
      error
    );


    if (industrialCount) {
      industrialCount.textContent =
        "0 industrial features";
    }


    if (alerts) {
      alerts.innerHTML = `
        <div class="empty error">
          ${escapeHtml(
            error?.message ||
            "Failed to load state data."
          )}
        </div>
      `;
    }


    /*
     * Clear stale clusters from the dashboard.
     */
    state.clusters = [];

    renderStats(
      state.clusters
    );

    renderAlerts(
      state.clusters,
      selectCluster
    );

    renderTable(
      state.clusters,
      selectCluster
    );

    updateFireSource();

    updateIndustrialSource();
  }
}


/* ============================================================
   Map positioning
   ============================================================ */

function centerMapOnState(
  bboxString
) {
  if (
    !state.map ||
    !bboxString
  ) {
    return;
  }


  const coordinates =
    String(
      bboxString
    )
      .split(",")
      .map(Number);


  if (
    coordinates.length !== 4 ||
    coordinates.some(
      (value) =>
        !Number.isFinite(value)
    )
  ) {
    console.warn(
      "Invalid state bbox:",
      bboxString
    );

    return;
  }


  const [
    west,
    south,
    east,
    north,
  ] = coordinates;


  state.map.fitBounds(
    [
      [west, south],
      [east, north],
    ],
    {
      padding: 40,
      duration: 700,
      maxZoom: 9,
    }
  );
}


/* ============================================================
   Refresh
   ============================================================ */

document
  .querySelector(
    "#refresh-button"
  )
  ?.addEventListener(
    "click",
    async () => {

      const button =
        document.querySelector(
          "#refresh-button"
        );


      if (button) {
        button.disabled =
          true;
      }


      try {

        await selectState(
          state.selectedState ||
          "Haryana"
        );

      } finally {

        if (button) {
          button.disabled =
            false;
        }
      }
    }
  );


/* ============================================================
   Industrial popup
   ============================================================ */

function handleIndustrialClick(
  feature,
  lngLat
) {
  if (!state.map) {
    return;
  }


  const properties =
    feature?.properties ||
    {};


  const name =
    properties.name ||
    "Industrial area";


  const category =
    properties.industry_category ||
    "Industrial land use";


  const sourceState =
    properties.source_state ||
    state.selectedState ||
    "Unknown";


  new maplibregl.Popup({
    closeButton:
      false,

    offset:
      8,
  })
    .setLngLat(
      lngLat
    )
    .setHTML(`
      <div class="map-popup">

        <strong>
          ${escapeHtml(
            name
          )}
        </strong>

        <div
          style="
            margin-top: 5px;
            color: #666;
            font-size: 10px;
          "
        >
          ${escapeHtml(
            formatLabel(
              category
            )
          )}
        </div>

        <div
          style="
            margin-top: 3px;
            color: #999;
            font-size: 9px;
          "
        >
          ${escapeHtml(
            sourceState
          )}
        </div>

      </div>
    `)
    .addTo(
      state.map
    );
}


/* ============================================================
   Startup
   ============================================================ */

async function init() {
  try {

    /*
     * 1. Initialize MapLibre first.
     */
    initializeMap(
      selectCluster,
      handleIndustrialClick
    );


    /*
     * 2. Register selector events.
     */
    setupStateSelector();


    /*
     * 3. Load available states.
     *
     * This also explicitly enables the <select>.
     */
    await populateStates();


    /*
     * 4. Backend health check.
     *
     * Don't let a health-check failure prevent
     * the actual state request from running.
     */
    try {

      await loadHealth();

      console.log(
        "[Fireline] Backend healthy."
      );

    } catch (healthError) {

      console.warn(
        "[Fireline] Backend health check failed:",
        healthError
      );
    }


    /*
     * 5. Load the selected state.
     */
    await selectState(
      state.selectedState ||
      "Haryana"
    );


  } catch (error) {

    console.error(
      "Dashboard initialization failed:",
      error
    );


    /*
     * Make sure the selector is usable even if
     * initialization encounters an unexpected error.
     */
    const selector =
      document.querySelector(
        "#state-select"
      );

    if (selector) {
      selector.disabled =
        false;
    }


    const alerts =
      document.querySelector(
        "#alerts"
      );


    if (alerts) {

      alerts.innerHTML = `
        <div class="empty error">
          ${escapeHtml(
            error?.message ||
            "Dashboard initialization failed."
          )}
        </div>
      `;
    }
  }
}


/* ============================================================
   HTML escaping
   ============================================================ */

function escapeHtml(
  value
) {
  return String(
    value ?? ""
  )
    .replaceAll(
      "&",
      "&amp;"
    )
    .replaceAll(
      "<",
      "&lt;"
    )
    .replaceAll(
      ">",
      "&gt;"
    )
    .replaceAll(
      '"',
      "&quot;"
    )
    .replaceAll(
      "'",
      "&#039;"
    );
}


/* ============================================================
   Start application
   ============================================================ */

init();
