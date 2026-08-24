import {
  formatLabel,
  formatDistance,
  riskClass,
} from "./utils.js";


export function renderTable(
  clusters,
  onSelectCluster
) {
  const table =
    document.querySelector(
      "#clusters-table"
    );

  if (!table) {
    return;
  }


  const sorted =
    [...clusters]
      .sort(
        (a, b) =>
          Number(
            b.risk_score
          ) -
          Number(
            a.risk_score
          )
      );


  table.innerHTML =
    sorted
      .map(cluster => {

        const risk =
          Number(
            cluster.risk_score
          );


        return `
          <tr
            class="cluster-row"
            data-cluster-id="${cluster.cluster_id}"
          >

            <td>
              #${cluster.cluster_id}
            </td>

            <td>
              <span
                class="classification"
              >
                ${formatLabel(
                  cluster.label
                )}
              </span>
            </td>

            <td class="mono">
              ${Number(
                cluster.max_frp ||
                0
              ).toFixed(2)}
            </td>

            <td>
              ${cluster.distinct_days}
              ${
                cluster.distinct_days ===
                1
                  ? "day"
                  : "days"
              }
            </td>

            <td class="mono">
              ${formatDistance(
                cluster
                  .min_distance_to_industrial_m
              )}
            </td>

            <td>
              <span
                class="${riskClass(
                  risk
                )}"
              >
                ${risk.toFixed(1)}
              </span>
            </td>

          </tr>
        `;
      })
      .join("");


  table
    .querySelectorAll(
      ".cluster-row"
    )
    .forEach(row => {

      row.addEventListener(
        "click",
        () => {

          onSelectCluster(
            Number(
              row.dataset
                .clusterId
            )
          );

        }
      );

    });
}
