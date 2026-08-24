import { loadIndustrial } from "./api.js";
import { state } from "./state.js";


export async function loadIndustrialForState(
  stateName
) {
  try {
    const data =
      await loadIndustrial(
        stateName
      );

    state.industrialData =
      data;

    console.log(
      `Industrial features for ${stateName}:`,
      data.features?.length || 0
    );

    return data;

  } catch (error) {
    console.error(
      `Failed to load industrial data for ${stateName}:`,
      error
    );

    state.industrialData = {
      type: "FeatureCollection",
      state: stateName,
      feature_count: 0,
      features: [],
    };

    throw error;
  }
}
