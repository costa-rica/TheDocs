const storageKey = "thedocs-theme";
const root = document.documentElement;
const button = document.getElementById("themeToggle");

const applyTheme = (theme) => {
  root.classList.remove("theme-dark", "theme-light");
  root.classList.add(theme);
};

const saved = localStorage.getItem(storageKey);
if (saved === "theme-light" || saved === "theme-dark") {
  applyTheme(saved);
} else {
  applyTheme("theme-dark");
}

if (button) {
  button.addEventListener("click", () => {
    const next = root.classList.contains("theme-dark") ? "theme-light" : "theme-dark";
    applyTheme(next);
    localStorage.setItem(storageKey, next);
  });
}
