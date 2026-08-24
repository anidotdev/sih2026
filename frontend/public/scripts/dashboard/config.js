const config =
    window.__FIRELINE_CONFIG__ || {};

export const API_URL =
    config.API_URL ||
    "http://127.0.0.1:8000";

export const FIRMS_DAYS = 5;

console.log(
    "[Fireline] API:",
    API_URL
);
