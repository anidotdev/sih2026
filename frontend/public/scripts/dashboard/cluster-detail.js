import {
  formatLabel,
  formatDistance,
} from "./utils.js";


export function createClusterSelector(
  getClusters,
  getMap
) {
  return function selectCluster(
    clusterId
  ) {
    const clusters =
      getClusters();

    const map =
      getMap();


    const cluster =
      clusters.find(
        item =>
          Number(
            item.cluster_id
          ) ===
          Number(clusterId)
      );


    if (!cluster) {
      console.warn(
        "Cluster not found:",
        clusterId
      );

      return;
    }


    /*
     * Store selected cluster.
     */
    window.dispatchEvent(
      new CustomEvent(
        "fireline:cluster-selected",
        {
          detail: {
            clusterId:
              Number(clusterId),
          },
        }
      )
    );


    const detail =
      document.querySelector(
        "#cluster-detail"
      );


    if (detail) {
      detail.classList.remove(
        "hidden"
      );
    }


    const title =
      document.querySelector(
        "#detail-title"
      );

    const label =
      document.querySelector(
        "#detail-label"
      );

    const risk =
      document.querySelector(
        "#detail-risk"
      );

    const frp =
      document.querySelector(
        "#detail-frp"
      );

    const persistence =
      document.querySelector(
        "#detail-persistence"
      );

    const distance =
      document.querySelector(
        "#detail-distance"
      );

    const confidence =
      document.querySelector(
        "#detail-confidence"
      );

    const reason =
      document.querySelector(
        "#detail-reason-text"
      );


    if (title) {
      title.textContent =
        `Cluster #${cluster.cluster_id}`;
    }

    if (label) {
      label.textContent =
        formatLabel(
          cluster.label
        );
    }

    if (risk) {
      risk.textContent =
        Number(
          cluster.risk_score
        ).toFixed(1);
    }

    if (frp) {
      frp.textContent =
        Number(
          cluster.max_frp
        ).toFixed(2);
    }

    if (persistence) {
      persistence.textContent =
        `${cluster.distinct_days} ${
          cluster.distinct_days === 1
            ? "day"
            : "days"
        }`;
    }

    if (distance) {
      distance.textContent =
        formatDistance(
          cluster
            .min_distance_to_industrial_m
        );
    }

    if (confidence) {
      confidence.textContent =
        formatLabel(
          cluster.confidence
        );
    }

    if (reason) {
      reason.textContent =
        cluster.reason || "—";
    }


    /*
     * Move map to the actual cluster.
     */
    const lat =
      Number(
        cluster.centroid_lat
      );

    const lon =
      Number(
        cluster.centroid_lon
      );


    if (
      map &&
      Number.isFinite(lat) &&
      Number.isFinite(lon)
    ) {

      map.flyTo({
        center: [
          lon,
          lat,
        ],

        zoom:
          Math.max(
            map.getZoom(),
            12
          ),

        duration:
          1000,

        essential:
          true,
      });


      /*
       * Add popup after the camera begins moving.
       */
      new maplibregl.Popup({
        closeButton:
          true,

        offset:
          14,

        closeOnClick:
          false,
      })
        .setLngLat([
          lon,
          lat,
        ])
        .setHTML(`
          <div class="map-popup">
            <strong>
              Cluster #${cluster.cluster_id}
            </strong>

            <div
              style="
                margin-top: 4px;
                color: #666;
                font-size: 11px;
              "
            >
              ${formatLabel(
                cluster.label
              )}
            </div>

            <div
              style="
                margin-top: 4px;
                font-size: 11px;
              "
            >
              Risk ${Number(
                cluster.risk_score
              ).toFixed(1)}
            </div>
          </div>
        `)
        .addTo(map);
    }
  };
}


export function setupDetailClose() {
  document
    .querySelector(
      "#close-detail"
    )
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
}
