import { loadIndustrial } from "./api.js";
import { state } from "./state.js";


export async function loadIndustrialForState(
  stateName
) {
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
}
