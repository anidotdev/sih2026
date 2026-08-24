import { MAP_STYLE } from "./config.js";
import { state } from "./state.js";


let eventsBound = false;


/* ============================================================
   Cluster selection event
   ============================================================ */

window.addEventListener(
  "fireline:cluster-selected",
  (event) => {
    state.selectedClusterId =
      Number(event.detail.clusterId);

    updateFireSource();
  }
);


/* ============================================================
   Initialize Map
   ============================================================ */

export function initializeMap(
  onSelectCluster,
  onIndustrialClick
) {
  state.map =
    new maplibregl.Map({
      container: "map",

      // Always light mode.
      style: MAP_STYLE,

      center: [
        77.2,
        28.4,
      ],

      zoom: 7,

      attributionControl: true,
    });


  state.map.addControl(
    new maplibregl.NavigationControl(),
    "top-right"
  );


  state.map.once(
    "load",
    () => {
      console.log(
        "MapLibre loaded"
      );

      ensureIndustrialLayers();
      ensureFireLayers();

      bindMapEvents(
        onSelectCluster,
        onIndustrialClick
      );

      updateIndustrialSource();
      updateFireSource();
    }
  );


  return state.map;
}


/* ============================================================
   Industrial Source
   ============================================================ */

function ensureIndustrialSource() {
  if (
    !state.map.getSource(
      "industrial"
    )
  ) {
    state.map.addSource(
      "industrial",
      {
        type: "geojson",

        data:
          state.industrialData,
      }
    );
  }
}


/* ============================================================
   Industrial Layers
   ============================================================ */

function ensureIndustrialLayers() {
  if (!state.map) {
    return;
  }


  ensureIndustrialSource();


  /*
   * Polygon / MultiPolygon
   */

  if (
    !state.map.getLayer(
      "industrial-fill"
    )
  ) {
    state.map.addLayer({
      id:
        "industrial-fill",

      type:
        "fill",

      source:
        "industrial",

      filter: [
        "any",

        [
          "==",
          ["geometry-type"],
          "Polygon",
        ],

        [
          "==",
          ["geometry-type"],
          "MultiPolygon",
        ],
      ],

      paint: {
        "fill-color":
          "#64748b",

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


  /*
   * Polygon outline
   */

  if (
    !state.map.getLayer(
      "industrial-outline"
    )
  ) {
    state.map.addLayer({
      id:
        "industrial-outline",

      type:
        "line",

      source:
        "industrial",

      filter: [
        "any",

        [
          "==",
          ["geometry-type"],
          "Polygon",
        ],

        [
          "==",
          ["geometry-type"],
          "MultiPolygon",
        ],
      ],

      paint: {
        "line-color":
          "#64748b",

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

        "line-opacity":
          0.55,
      },
    });
  }


  /*
   * Point features
   */

  if (
    !state.map.getLayer(
      "industrial-points"
    )
  ) {
    state.map.addLayer({
      id:
        "industrial-points",

      type:
        "circle",

      source:
        "industrial",

      filter: [
        "==",
        ["geometry-type"],
        "Point",
      ],

      paint: {
        "circle-radius": [
          "interpolate",
          ["linear"],
          ["zoom"],

          6,
          2.5,

          10,
          4,

          14,
          6,
        ],

        "circle-color":
          "#64748b",

        "circle-opacity":
          0.8,

        "circle-stroke-width":
          1,

        "circle-stroke-color":
          "#ffffff",
      },
    });
  }


  /*
   * Line features
   */

  if (
    !state.map.getLayer(
      "industrial-lines"
    )
  ) {
    state.map.addLayer({
      id:
        "industrial-lines",

      type:
        "line",

      source:
        "industrial",

      filter: [
        "==",
        ["geometry-type"],
        "LineString",
      ],

      paint: {
        "line-color":
          "#64748b",

        "line-width":
          1.5,

        "line-opacity":
          0.6,
      },
    });
  }
}


/* ============================================================
   Update Industrial Source
   ============================================================ */

export function updateIndustrialSource() {
  if (
    !state.map ||
    !state.map.isStyleLoaded()
  ) {
    return;
  }


  ensureIndustrialLayers();


  const source =
    state.map.getSource(
      "industrial"
    );


  if (!source) {
    return;
  }


  source.setData(
    state.industrialData
  );


  const counter =
    document.querySelector(
      "#industrial-count"
    );


  if (counter) {
    counter.textContent =
      `${
        state
          .industrialData
          .features
          ?.length || 0
      } industrial features`;
  }
}


/* ============================================================
   Fire Source
   ============================================================ */

function ensureFireSource() {
  if (
    !state.map.getSource(
      "fire-clusters"
    )
  ) {
    state.map.addSource(
      "fire-clusters",
      {
        type: "geojson",

        data: {
          type:
            "FeatureCollection",

          features: [],
        },
      }
    );
  }
}


/* ============================================================
   Fire Layers
   ============================================================ */

function ensureFireLayers() {
  if (!state.map) {
    return;
  }


  ensureFireSource();


  /*
   * Heatmap
   */

  if (
    !state.map.getLayer(
      "fire-heatmap"
    )
  ) {
    state.map.addLayer({
      id:
        "fire-heatmap",

      type:
        "heatmap",

      source:
        "fire-clusters",

      maxzoom:
        12,

      paint: {
        "heatmap-weight": [
          "interpolate",
          ["linear"],
          ["get", "risk_score"],

          0,
          0.10,

          20,
          0.25,

          40,
          0.50,

          70,
          0.90,

          100,
          1.20,
        ],

        "heatmap-intensity": [
          "interpolate",
          ["linear"],
          ["zoom"],

          5,
          0.55,

          8,
          0.8,

          10,
          1.0,

          12,
          1.2,
        ],

        "heatmap-radius": [
          "interpolate",
          ["linear"],
          ["zoom"],

          5,
          14,

          7,
          20,

          9,
          28,

          11,
          38,

          13,
          50,
        ],

        "heatmap-color": [
          "interpolate",
          ["linear"],
          ["heatmap-density"],

          0,
          "rgba(255,255,255,0)",

          0.15,
          "rgba(254,240,138,0.20)",

          0.35,
          "rgba(250,204,21,0.35)",

          0.55,
          "rgba(245,158,11,0.50)",

          0.75,
          "rgba(239,68,68,0.65)",

          1,
          "rgba(185,28,28,0.80)",
        ],

        "heatmap-opacity":
          0.65,
      },
    });
  }


  /*
   * Fire markers
   */

  if (
    !state.map.getLayer(
      "fire-clusters"
    )
  ) {
    state.map.addLayer({
      id:
        "fire-clusters",

      type:
        "circle",

      source:
        "fire-clusters",

      paint: {
        "circle-radius": [
          "case",

          [
            "==",
            ["get", "cluster_id"],
            state.selectedClusterId,
          ],

          14,

          [
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
        ],

        "circle-color": [
          "case",

          [
            "==",
            ["get", "cluster_id"],
            state.selectedClusterId,
          ],

          "#dc2626",

          [
            ">=",
            ["get", "risk_score"],
            70,
          ],

          "#dc2626",

          [
            ">=",
            ["get", "risk_score"],
            40,
          ],

          "#f59e0b",

          "#9ca3af",
        ],

        "circle-opacity":
          1,

        "circle-stroke-width": [
          "case",

          [
            "==",
            ["get", "cluster_id"],
            state.selectedClusterId,
          ],

          3,

          2,
        ],

        "circle-stroke-color":
          "#ffffff",

        "circle-stroke-opacity":
          1,
      },
    });
  }


  /*
   * Selected cluster ring
   */

  if (
    !state.map.getLayer(
      "selected-cluster-ring"
    )
  ) {
    state.map.addLayer({
      id:
        "selected-cluster-ring",

      type:
        "circle",

      source:
        "fire-clusters",

      filter: [
        "==",
        ["get", "cluster_id"],
        state.selectedClusterId,
      ],

      paint: {
        "circle-radius":
          19,

        "circle-color":
          "rgba(220,38,38,0.08)",

        "circle-stroke-color":
          "#dc2626",

        "circle-stroke-width":
          2.5,

        "circle-stroke-opacity":
          0.9,
      },
    });
  }
}


/* ============================================================
   Update Fire Source
   ============================================================ */

export function updateFireSource() {
  if (
    !state.map ||
    !state.map.isStyleLoaded()
  ) {
    return;
  }


  ensureFireLayers();


  const source =
    state.map.getSource(
      "fire-clusters"
    );


  if (!source) {
    return;
  }


  const features =
    state.clusters.map(
      cluster => ({
        type:
          "Feature",

        id:
          Number(
            cluster.cluster_id
          ),

        geometry: {
          type:
            "Point",

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
            Number(
              cluster.cluster_id
            ),

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
      })
    );


  source.setData({
    type:
      "FeatureCollection",

    features,
  });


  const ring =
    state.map.getLayer(
      "selected-cluster-ring"
    );


  if (ring) {
    state.map.setFilter(
      "selected-cluster-ring",
      [
        "==",
        ["get", "cluster_id"],
        state.selectedClusterId,
      ]
    );
  }
}


/* ============================================================
   Map Events
   ============================================================ */

function bindMapEvents(
  onSelectCluster,
  onIndustrialClick
) {
  if (eventsBound) {
    return;
  }

  eventsBound = true;


  /* ----------------------------------------------------------
     Fire marker events
     ---------------------------------------------------------- */

  state.map.on(
    "mouseenter",
    "fire-clusters",
    () => {
      state.map.getCanvas()
        .style.cursor =
        "pointer";
    }
  );


  state.map.on(
    "mouseleave",
    "fire-clusters",
    () => {
      state.map.getCanvas()
        .style.cursor =
        "";
    }
  );


  state.map.on(
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
          feature.properties
            .cluster_id
        );


      onSelectCluster(
        clusterId
      );
    }
  );


  /* ----------------------------------------------------------
     Industrial events
     ---------------------------------------------------------- */

  const industrialLayers = [
    "industrial-fill",
    "industrial-points",
    "industrial-lines",
  ];


  for (
    const layer
    of industrialLayers
  ) {

    state.map.on(
      "mouseenter",
      layer,
      () => {
        state.map.getCanvas()
          .style.cursor =
          "pointer";
      }
    );


    state.map.on(
      "mouseleave",
      layer,
      () => {
        state.map.getCanvas()
          .style.cursor =
          "";
      }
    );


    state.map.on(
      "click",
      layer,
      event => {
        const feature =
          event.features?.[0];

        if (!feature) {
          return;
        }


        onIndustrialClick(
          feature,
          event.lngLat
        );
      }
    );
  }
}
