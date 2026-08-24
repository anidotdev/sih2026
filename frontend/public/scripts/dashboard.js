const API_URL =
  import.meta.env.PUBLIC_API_URL ||
  "http://127.0.0.1:8000";

console.log(
  "Fireline API:",
  API_URL
);

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
    async event => {
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
      data.states || [];


    if (!state.states.length) {
      throw new Error(
        "Backend returned no states."
      );
    }


    selector.innerHTML =
      state.states
        .map(
          item => `
            <option
              value="${item.name}"
            >
              ${item.name}
            </option>
          `
        )
        .join("");


    /*
     * Preserve Haryana as the initial state
     * if it exists.
     */
    const haryana =
      state.states.find(
        item =>
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


    console.log(
      `Loaded ${state.states.length} states`
    );


  } catch (error) {

    console.error(
      "Failed to load states:",
      error
    );


    /*
     * Keep the static Haryana option.
     * The map itself will still work.
     */
    state.selectedState =
      "Haryana";


    selector.innerHTML = `
      <option value="Haryana">
        Haryana
      </option>
    `;
  }
}


/* ============================================================
   State selection
   ============================================================ */

async function selectState(
  stateName
) {
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


  try {

    /*
     * Fetch fires and industrial data
     * at the same time.
     */
    const [
      fireData,
    ] = await Promise.all([
      loadFires(
        stateName
      ),

      loadIndustrialForState(
        stateName
      ),
    ]);


    state.clusters =
      fireData.clusters ||
      [];


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
     * Map may already be loaded.
     */
    updateIndustrialSource();
    updateFireSource();


    /*
     * Center the map on the selected state's
     * FIRMS bbox if the backend supplied it.
     */
    if (
      state.map &&
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


    const alerts =
      document.querySelector(
        "#alerts"
      );


    if (alerts) {
      alerts.innerHTML = `
        <div class="empty error">
          ${escapeHtml(
            error.message
          )}
        </div>
      `;
    }
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
    bboxString
      .split(",")
      .map(Number);


  if (
    coordinates.length !== 4 ||
    coordinates.some(
      value =>
        !Number.isFinite(value)
    )
  ) {
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
          state.selectedState
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
  const properties =
    feature.properties || {};


  const name =
    properties.name ||
    "Industrial area";


  const category =
    properties.industry_category ||
    "Industrial land use";


  const sourceState =
    properties.source_state ||
    state.selectedState;


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
   Start
   ============================================================ */

async function init() {
  try {

    /*
     * 1. Initialize the map FIRST.
     *
     * This means a failure in /states cannot
     * prevent MapLibre from loading.
     */
    initializeMap(
      selectCluster,
      handleIndustrialClick
    );


    /*
     * 2. Setup the selector.
     */
    setupStateSelector();


    /*
     * 3. Load available states.
     */
    await populateStates();


    /*
     * 4. Backend health is checked independently.
     */
    await loadHealth();


    /*
     * 5. Load initial state.
     */
    await selectState(
      state.selectedState
    );


  } catch (error) {

    console.error(
      "Dashboard initialization failed:",
      error
    );


    const alerts =
      document.querySelector(
        "#alerts"
      );


    if (alerts) {
      alerts.innerHTML = `
        <div class="empty error">
          ${escapeHtml(
            error.message
          )}
        </div>
      `;
    }
  }
}


function escapeHtml(
  value
) {
  return String(value)
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


init();
