import {
  formatLabel,
  escapeHtml,
} from "./utils.js";


export function renderAlerts(
  clusters,
  onSelectCluster
) {
  const container =
    document.querySelector(
      "#alerts"
    );

  if (!container) {
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


  container.innerHTML =
    sorted
      .map(cluster => {
        const risk =
          Number(
            cluster.risk_score
          );

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

            <div
              class="alert-indicator ${status}"
            ></div>

            <div
              class="alert-content"
            >

              <div
                class="alert-top"
              >
                <span>
                  Cluster #${cluster.cluster_id}
                </span>

                <strong>
                  ${risk.toFixed(1)}
                </strong>
              </div>


              <div
                class="alert-label"
              >
                ${formatLabel(
                  cluster.label
                )}
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

          onSelectCluster(
            Number(
              element.dataset
                .clusterId
            )
          );
        }
      );

    });
}
