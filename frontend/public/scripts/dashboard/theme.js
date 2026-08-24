export function initializeTheme() {
  const toggle =
    document.querySelector(
      "#theme-toggle"
    );

  const icon =
    document.querySelector(
      "#theme-icon"
    );


  function getPreferredTheme() {
    const saved =
      localStorage.getItem(
        "fireline-theme"
      );

    if (
      saved === "light" ||
      saved === "dark"
    ) {
      return saved;
    }

    return window.matchMedia(
      "(prefers-color-scheme: dark)"
    ).matches
      ? "dark"
      : "light";
  }


  function applyTheme(theme) {
    document.documentElement.dataset.theme =
      theme;

    localStorage.setItem(
      "fireline-theme",
      theme
    );

    if (icon) {
      icon.textContent =
        theme === "dark"
          ? "☀"
          : "☾";
    }
  }


  applyTheme(
    getPreferredTheme()
  );


  toggle?.addEventListener(
    "click",
    () => {
      const current =
        document.documentElement.dataset.theme;

      applyTheme(
        current === "dark"
          ? "light"
          : "dark"
      );
    }
  );
}
