const themeToggle = document.querySelector("[data-theme-toggle]");
const themeLabel = document.querySelector("[data-theme-label]");
const themeIcon = document.querySelector(".theme-icon");

function applyTheme(theme) {
  const isDark = theme === "dark";
  document.documentElement.dataset.theme = isDark ? "dark" : "light";
  themeToggle.setAttribute("aria-pressed", String(isDark));
  themeLabel.textContent = isDark ? "Modo claro" : "Modo escuro";
  themeIcon.textContent = isDark ? "☀" : "☾";
  window.dispatchEvent(new Event("financeflow-theme-change"));
}

applyTheme(localStorage.getItem("financeflow-theme") || "light");
themeToggle.addEventListener("click", () => {
  const nextTheme = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
  localStorage.setItem("financeflow-theme", nextTheme);
  applyTheme(nextTheme);
});
