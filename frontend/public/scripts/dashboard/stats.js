export function renderStats(
  clusters
) {
  const active =
    clusters.length;


  const highRisk =
    clusters.filter(
      cluster =>
        Number(
          cluster.risk_score
        ) >= 70
    ).length;


  const persistent =
    clusters.filter(
      cluster =>
        cluster.is_persistent
    ).length;


  const maxFrp =
    clusters.length
      ? Math.max(
          ...clusters.map(
            cluster =>
              Number(
                cluster.max_frp
              ) || 0
          )
        )
      : 0;


  const activeElement =
    document.querySelector(
      "#active-clusters"
    );

  const highRiskElement =
    document.querySelector(
      "#high-risk"
    );

  const persistentElement =
    document.querySelector(
      "#persistent"
    );

  const maxFrpElement =
    document.querySelector(
      "#max-frp"
    );

  const alertCountElement =
    document.querySelector(
      "#alert-count"
    );


  if (activeElement) {
    activeElement.textContent =
      active;
  }

  if (highRiskElement) {
    highRiskElement.textContent =
      highRisk;
  }

  if (persistentElement) {
    persistentElement.textContent =
      persistent;
  }

  if (maxFrpElement) {
    maxFrpElement.textContent =
      maxFrp.toFixed(2);
  }

  if (alertCountElement) {
    alertCountElement.textContent =
      active;
  }
}
