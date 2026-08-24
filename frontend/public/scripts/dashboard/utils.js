export function formatLabel(value) {
  if (!value) {
    return "—";
  }

  return String(value)
    .replaceAll("_", " ")
    .replace(
      /\b\w/g,
      letter => letter.toUpperCase()
    );
}


export function formatDistance(value) {
  if (
    value === null ||
    value === undefined ||
    !Number.isFinite(Number(value))
  ) {
    return "—";
  }

  return `${(
    Number(value) / 1000
  ).toFixed(1)} km`;
}


export function riskClass(score) {
  score = Number(score);

  if (score >= 70) {
    return "risk-high";
  }

  if (score >= 40) {
    return "risk-medium";
  }

  return "risk-low";
}


export function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
