const API_URL = "http://127.0.0.1:8000";

const BBOX = "76.5,27.5,78.0,29.0";
const DAYS = 5;

let map;
let clusters = [];

let industrialData = {
  type: "FeatureCollection",
  features: [],
};


/* ============================================================
   Theme
   ============================================================ */

const themeToggle =
  document.querySelector("#theme-toggle");

const themeIcon =
  document.querySelector("#theme-icon");

function getPreferredTheme() {
  const saved =
    localStorage.getItem("fireline-theme");

  if (saved === "light" || saved === "dark") {
    return saved;
  }

  return window.matchMedia(
    "(prefers-color-scheme: dark)"
  ).matches
    ? "dark"
    : "light";
}

function getMapStyle() {
  return "https://tiles.openfreemap.org/styles/positron";
}

function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;

  localStorage.setItem(
    "fireline-theme",
    theme
  );

  if (themeIcon) {
    themeIcon.textContent =
      theme === "dark" ? "☀" : "☾";
  }
}

applyTheme(getPreferredTheme());

themeToggle?.addEventListener(
  "click",
  () => {
    const current =
      document.documentElement.dataset.theme;

    applyTheme(
      current === "dark"
        ? "light"
        : "dark"
    );
  }
);


/* ============================================================
   API
   ============================================================ */

async function loadHealth() {
  const response =
    await fetch(`${API_URL}/health`);

  if (!response.ok) {
    throw new Error(
      "Backend health check failed"
    );
  }

  return response.json();
}


async function loadFires() {
  const params = new URLSearchParams({
    bbox: BBOX,
    days: DAYS,
  });

  /*
   * FIRMS data and industrial reference data
   * are fetched in parallel.
   */
  const [
    firesResponse,
    industrialResponse,
  ] = await Promise.all([
    fetch(
      `${API_URL}/fires?${params.toString()}`
    ),
    fetch(`${API_URL}/industrial`),
  ]);

  if (!firesResponse.ok) {
    throw new Error(
      `FIRMS API returned ${firesResponse.status}`
    );
  }

  if (!industrialResponse.ok) {
    throw new Error(
      `Industrial API returned ${industrialResponse.status}`
    );
  }

  const fireData =
    await firesResponse.json();

  industrialData =
    await industrialResponse.json();

  clusters =
    fireData.clusters || [];

  console.log(
    "FIRMS clusters:",
    clusters
  );

  console.log(
    "Industrial features:",
    industrialData.features?.length || 0
  );

  renderStats();
  renderAlerts();
  renderTable();
  renderMap();
}


/* ============================================================
   Statistics
   ============================================================ */

function renderStats() {
  const active = clusters.length;

  const highRisk = clusters.filter(
    cluster =>
      Number(cluster.risk_score) >= 70
  ).length;

  const persistent = clusters.filter(
    cluster =>
      cluster.is_persistent
  ).length;

  const maxFrp = clusters.length
    ? Math.max(
        ...clusters.map(
          cluster =>
            Number(cluster.max_frp) || 0
        )
      )
    : 0;

  document.querySelector(
    "#active-clusters"
  ).textContent = active;

  document.querySelector(
    "#high-risk"
  ).textContent = highRisk;

  document.querySelector(
    "#persistent"
  ).textContent = persistent;

  document.querySelector(
    "#max-frp"
  ).textContent =
    maxFrp.toFixed(2);

  document.querySelector(
    "#alert-count"
  ).textContent = active;
}


/* ============================================================
   Alerts
   ============================================================ */

function renderAlerts() {
  const container =
    document.querySelector("#alerts");

  const sorted = [...clusters]
    .sort(
      (a, b) =>
        Number(b.risk_score) -
        Number(a.risk_score)
    )
    .slice(0, 8);

  if (!sorted.length) {
    container.innerHTML = `
      <div class="empty">
        No active clusters found.
      </div>
    `;

    return;
  }

  container.innerHTML = sorted
    .map(cluster => {
      const risk =
        Number(cluster.risk_score);

      const status =
        risk >= 70
          ? "high"
          : risk >= 40
          ? "medium"
          : "low";

      return `
        <article
          class="alert clickable-alert"
          data-cluster-id="${cluster.cluster_id}"
        >
          <div class="alert-indicator ${status}"></div>

          <div class="alert-content">
            <div class="alert-top">
              <span>
                Cluster #${cluster.cluster_id}
              </span>

              <strong>
                ${risk.toFixed(1)}
              </strong>
            </div>

            <div class="alert-label">
              ${formatLabel(cluster.label)}
            </div>

            <p>
              ${escapeHtml(
                cluster.reason || ""
              )}
            </p>
          </div>
        </article>
      `;
    })
    .join("");

  container
    .querySelectorAll(
      ".clickable-alert"
    )
    .forEach(element => {
      element.addEventListener(
        "click",
        () => {
          const id =
            Number(
              element.dataset.clusterId
            );

          selectCluster(id);
        }
      );
    });
}


/* ============================================================
   Table
   ============================================================ */

function renderTable() {
  const table =
    document.querySelector(
      "#clusters-table"
    );

  const sorted = [...clusters].sort(
    (a, b) =>
      Number(b.risk_score) -
      Number(a.risk_score)
  );

  table.innerHTML = sorted
    .map(cluster => {
      const risk =
        Number(cluster.risk_score);

      return `
        <tr
          class="cluster-row"
          data-cluster-id="${cluster.cluster_id}"
        >
          <td>
            #${cluster.cluster_id}
          </td>

          <td>
            <span class="classification">
              ${formatLabel(
                cluster.label
              )}
            </span>
          </td>

          <td class="mono">
            ${Number(
              cluster.max_frp || 0
            ).toFixed(2)}
          </td>

          <td>
            ${cluster.distinct_days}
            ${
              cluster.distinct_days === 1
                ? "day"
                : "days"
            }
          </td>

          <td class="mono">
            ${formatDistance(
              cluster.min_distance_to_industrial_m
            )}
          </td>

          <td>
            <span
              class="${riskClass(risk)}"
            >
              ${risk.toFixed(1)}
            </span>
          </td>
        </tr>
      `;
    })
    .join("");

  table
    .querySelectorAll(".cluster-row")
    .forEach(row => {
      row.addEventListener(
        "click",
        () => {
          const id =
            Number(
              row.dataset.clusterId
            );

          selectCluster(id);
        }
      );
    });
}


/* ============================================================
   Map initialization
   ============================================================ */

function initMap() {
  map = new maplibregl.Map({
    container: "map",

    style: getMapStyle(),

    center: [77.2, 28.4],

    zoom: 7,

    attributionControl: true,
  });

  map.addControl(
    new maplibregl.NavigationControl(),
    "top-right"
  );

  map.on("load", () => {
    renderMap();
    bindMapEvents();
  });
}


/* ============================================================
   Map events
   ============================================================ */

function bindMapEvents() {
  /*
   * Avoid attaching duplicate listeners after
   * a theme change.
   */
  map.off(
    "mouseenter",
    "fire-clusters"
  );

  map.off(
    "mouseleave",
    "fire-clusters"
  );

  map.off(
    "click",
    "fire-clusters"
  );

  map.off(
    "mouseenter",
    "industrial-fill"
  );

  map.off(
    "mouseleave",
    "industrial-fill"
  );

  map.off(
    "click",
    "industrial-fill"
  );


  /* ----------------------------------------------------------
     Fire clusters
     ---------------------------------------------------------- */

  map.on(
    "mouseenter",
    "fire-clusters",
    () => {
      map.getCanvas().style.cursor =
        "pointer";
    }
  );

  map.on(
    "mouseleave",
    "fire-clusters",
    () => {
      map.getCanvas().style.cursor =
        "";
    }
  );

  map.on(
    "click",
    "fire-clusters",
    event => {
      const feature =
        event.features?.[0];

      if (!feature) {
        return;
      }

      const clusterId =
        Number(
          feature.properties.cluster_id
        );

      selectCluster(clusterId);

      new maplibregl.Popup({
        closeButton: false,
        offset: 12,
      })
        .setLngLat(
          feature.geometry.coordinates
        )
        .setHTML(`
          <div class="map-popup">
            <strong>
              Cluster #${clusterId}
            </strong>
          </div>
        `)
        .addTo(map);
    }
  );


  /* ----------------------------------------------------------
     Industrial areas
     ---------------------------------------------------------- */

  map.on(
    "mouseenter",
    "industrial-fill",
    () => {
      map.getCanvas().style.cursor =
        "pointer";
    }
  );

  map.on(
    "mouseleave",
    "industrial-fill",
    () => {
      map.getCanvas().style.cursor =
        "";
    }
  );

  map.on(
    "click",
    "industrial-fill",
    event => {
      const feature =
        event.features?.[0];

      if (!feature) {
        return;
      }

      const properties =
        feature.properties || {};

      const name =
        properties.name ||
        "Industrial area";

      const landuse =
        properties.landuse ||
        "Industrial land use";

      new maplibregl.Popup({
        closeButton: false,
        offset: 8,
      })
        .setLngLat(
          event.lngLat
        )
        .setHTML(`
          <div class="map-popup">
            <strong>
              ${escapeHtml(name)}
            </strong>

            <div
              style="
                margin-top: 5px;
                color: #666;
                font-size: 10px;
              "
            >
              ${escapeHtml(landuse)}
            </div>
          </div>
        `)
        .addTo(map);
    }
  );
}


/* ============================================================
   Map layers
   ============================================================ */

function renderMap() {
  if (
    !map ||
    !map.isStyleLoaded()
  ) {
    return;
  }


  /* ----------------------------------------------------------
     OSM industrial source
     ---------------------------------------------------------- */

  if (
    !map.getSource("industrial")
  ) {
    map.addSource(
      "industrial",
      {
        type: "geojson",
        data: industrialData,
      }
    );
  } else {
    map
      .getSource("industrial")
      .setData(
        industrialData
      );
  }


  /* ----------------------------------------------------------
     Industrial polygons
     ---------------------------------------------------------- */

  if (
    !map.getLayer(
      "industrial-fill"
    )
  ) {
    map.addLayer({
      id: "industrial-fill",

      type: "fill",

      source: "industrial",

      paint: {
        "fill-color": "#64748b",

        "fill-opacity": [
          "interpolate",
          ["linear"],
          ["zoom"],

          6,
          0.06,

          9,
          0.10,

          12,
          0.16,

          15,
          0.23,
        ],
      },
    });
  }


  /* ----------------------------------------------------------
     Industrial outlines
     ---------------------------------------------------------- */

  if (
    !map.getLayer(
      "industrial-outline"
    )
  ) {
    map.addLayer({
      id: "industrial-outline",

      type: "line",

      source: "industrial",

      paint: {
        "line-color": "#64748b",

        "line-width": [
          "interpolate",
          ["linear"],
          ["zoom"],

          6,
          0.35,

          10,
          0.7,

          14,
          1.2,
        ],

        "line-opacity": 0.5,
      },
    });
  }


  /* ----------------------------------------------------------
     FIRMS cluster source
     ---------------------------------------------------------- */

  const features =
    clusters.map(cluster => ({
      type: "Feature",

      geometry: {
        type: "Point",

        coordinates: [
          Number(
            cluster.centroid_lon
          ),
          Number(
            cluster.centroid_lat
          ),
        ],
      },

      properties: {
        cluster_id:
          cluster.cluster_id,

        risk_score:
          Number(
            cluster.risk_score
          ) || 0,

        max_frp:
          Number(
            cluster.max_frp
          ) || 0,

        label:
          cluster.label ||
          "uncertain",
      },
    }));

  const fireGeoJSON = {
    type: "FeatureCollection",
    features,
  };


  if (
    !map.getSource(
      "fire-clusters"
    )
  ) {
    map.addSource(
      "fire-clusters",
      {
        type: "geojson",
        data: fireGeoJSON,
      }
    );
  } else {
    map
      .getSource(
        "fire-clusters"
      )
      .setData(
        fireGeoJSON
      );
  }


  /* ----------------------------------------------------------
     Heatmap
     ---------------------------------------------------------- */

  if (
    !map.getLayer(
      "fire-heatmap"
    )
  ) {
    map.addLayer({
      id: "fire-heatmap",

      type: "heatmap",

      source: "fire-clusters",

      maxzoom: 12,

      paint: {
        "heatmap-weight": [
          "interpolate",
          ["linear"],
          ["get", "risk_score"],

          0,
          0.15,

          20,
          0.35,

          40,
          0.6,

          70,
          1.0,

          100,
          1.4,
        ],

        "heatmap-intensity": [
          "interpolate",
          ["linear"],
          ["zoom"],

          5,
          0.65,

          8,
          0.9,

          10,
          1.1,

          12,
          1.35,
        ],

        "heatmap-radius": [
          "interpolate",
          ["linear"],
          ["zoom"],

          5,
          16,

          7,
          22,

          9,
          30,

          11,
          42,

          13,
          55,
        ],

        "heatmap-color": [
          "interpolate",
          ["linear"],
          ["heatmap-density"],

          0,
          "rgba(255,255,255,0)",

          0.12,
          "rgba(254,240,138,0.18)",

          0.30,
          "rgba(250,204,21,0.35)",

          0.50,
          "rgba(245,158,11,0.52)",

          0.70,
          "rgba(239,68,68,0.65)",

          0.88,
          "rgba(220,38,38,0.78)",

          1,
          "rgba(153,27,27,0.86)",
        ],

        "heatmap-opacity": 0.72,
      },
    });
  }


  /* ----------------------------------------------------------
     Cluster markers
     ---------------------------------------------------------- */

  if (
    !map.getLayer(
      "fire-clusters"
    )
  ) {
    map.addLayer({
      id: "fire-clusters",

      type: "circle",

      source: "fire-clusters",

      paint: {
        "circle-radius": [
          "interpolate",
          ["linear"],
          ["get", "risk_score"],

          0,
          5,

          40,
          7,

          70,
          10,

          100,
          13,
        ],

        "circle-color": [
          "step",
          ["get", "risk_score"],

          "#9ca3af",

          40,
          "#f59e0b",

          70,
          "#dc2626",
        ],

        "circle-opacity": 0.96,

        "circle-stroke-width": 1.5,

        "circle-stroke-color":
          "#ffffff",

        "circle-stroke-opacity": 0.92,
      },
    });
  }
}


/* ============================================================
   Cluster detail
   ============================================================ */

function selectCluster(clusterId) {
  const cluster =
    clusters.find(
      item =>
        Number(
          item.cluster_id
        ) === clusterId
    );

  if (!cluster) {
    return;
  }

  const detail =
    document.querySelector(
      "#cluster-detail"
    );

  if (!detail) {
    return;
  }

  detail.classList.remove(
    "hidden"
  );

  document.querySelector(
    "#detail-title"
  ).textContent =
    `Cluster #${cluster.cluster_id}`;

  document.querySelector(
    "#detail-label"
  ).textContent =
    formatLabel(
      cluster.label
    );

  document.querySelector(
    "#detail-risk"
  ).textContent =
    Number(
      cluster.risk_score
    ).toFixed(1);

  document.querySelector(
    "#detail-frp"
  ).textContent =
    Number(
      cluster.max_frp
    ).toFixed(2);

  document.querySelector(
    "#detail-persistence"
  ).textContent =
    `${cluster.distinct_days} ${
      cluster.distinct_days === 1
        ? "day"
        : "days"
    }`;

  document.querySelector(
    "#detail-distance"
  ).textContent =
    formatDistance(
      cluster.min_distance_to_industrial_m
    );

  document.querySelector(
    "#detail-confidence"
  ).textContent =
    formatLabel(
      cluster.confidence
    );

  document.querySelector(
    "#detail-reason"
  ).textContent =
    cluster.reason ||
    "—";

  const lat =
    Number(
      cluster.centroid_lat
    );

  const lon =
    Number(
      cluster.centroid_lon
    );

  if (
    Number.isFinite(lat) &&
    Number.isFinite(lon)
  ) {
    map.flyTo({
      center: [
        lon,
        lat,
      ],

      zoom: Math.max(
        map.getZoom(),
        9
      ),

      duration: 900,
    });
  }
}


/* ============================================================
   Helpers
   ============================================================ */

function formatLabel(value) {
  if (!value) {
    return "—";
  }

  return String(value)
    .replaceAll("_", " ")
    .replace(
      /\b\w/g,
      letter =>
        letter.toUpperCase()
    );
}


function formatDistance(value) {
  if (
    value === null ||
    value === undefined ||
    !Number.isFinite(
      Number(value)
    )
  ) {
    return "—";
  }

  return `${(
    Number(value) / 1000
  ).toFixed(1)} km`;
}


function riskClass(score) {
  score = Number(score);

  if (score >= 70) {
    return "risk-high";
  }

  if (score >= 40) {
    return "risk-medium";
  }

  return "risk-low";
}


function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}


/* ============================================================
   Detail close
   ============================================================ */

document
  .querySelector("#close-detail")
  ?.addEventListener(
    "click",
    () => {
      document
        .querySelector(
          "#cluster-detail"
        )
        ?.classList.add(
          "hidden"
        );
    }
  );


/* ============================================================
   Refresh
   ============================================================ */

document
  .querySelector("#refresh-button")
  ?.addEventListener(
    "click",
    async () => {
      const button =
        document.querySelector(
          "#refresh-button"
        );

      button.disabled = true;

      try {
        await loadFires();
      } catch (error) {
        console.error(error);
      } finally {
        button.disabled = false;
      }
    }
  );


/* ============================================================
   Start
   ============================================================ */

async function init() {
  try {
    await loadHealth();

    initMap();

    await loadFires();

  } catch (error) {
    console.error(error);

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

init();
