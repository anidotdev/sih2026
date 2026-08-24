const config =
    window.__FIRELINE_CONFIG__ || {};


/* ============================================================
   API
   ============================================================ */

export const API_URL =
    config.API_URL ||
    "http://127.0.0.1:8000";


/* ============================================================
   FIRMS
   ============================================================ */

export const FIRMS_DAYS = 5;


/* ============================================================
   MapLibre style
   ============================================================ */

export const MAP_STYLE = {
    version: 8,

    sources: {
        osm: {
            type: "raster",

            tiles: [
                "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
            ],

            tileSize: 256,

            attribution:
                "© OpenStreetMap contributors",
        },
    },

    layers: [
        {
            id: "osm",

            type: "raster",

            source: "osm",
        },
    ],
};


/* ============================================================
   Debug
   ============================================================ */

console.log(
    "[Fireline] API:",
    API_URL
);
