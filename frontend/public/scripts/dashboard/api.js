import { API_URL, FIRMS_DAYS } from "./config.js";

export async function loadHealth() {
  const response = await fetch(
    `${API_URL}/health`
  );

  if (!response.ok) {
    throw new Error(
      "Backend health check failed"
    );
  }

  return response.json();
}

export async function loadStates() {
  const response = await fetch(
    `${API_URL}/states`
  );

  if (!response.ok) {
    throw new Error(
      `States API returned ${response.status}`
    );
  }

  return response.json();
}

export async function loadFires(
  state,
  days = FIRMS_DAYS
) {
  const params = new URLSearchParams({
    state,
    days,
  });

  const response = await fetch(
    `${API_URL}/fires?${params.toString()}`
  );

  if (!response.ok) {
    const data = await response.json()
      .catch(() => null);

    throw new Error(
      data?.detail ||
      `FIRMS API returned ${response.status}`
    );
  }

  return response.json();
}

export async function loadIndustrial(
  state
) {
  const params = new URLSearchParams({
    state,
  });

  const response = await fetch(
    `${API_URL}/industrial?${params.toString()}`
  );

  if (!response.ok) {
    const data = await response.json()
      .catch(() => null);

    throw new Error(
      data?.detail ||
      `Industrial API returned ${response.status}`
    );
  }

  return response.json();
}
