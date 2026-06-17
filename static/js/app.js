// Minimal helpers. Most interactivity is via HTMX + Alpine.
document.addEventListener("htmx:configRequest", (e) => {
  const tok = document.querySelector("[name=csrfmiddlewaretoken]");
  if (tok) e.detail.headers["X-CSRFToken"] = tok.value;
});

function getCookie(name) {
  return document.cookie.split("; ").reduce((acc, c) => {
    const [k, v] = c.split("=");
    return k === name ? decodeURIComponent(v) : acc;
  }, null);
}
window.csrfToken = () => getCookie("csrftoken");

// Register PWA service worker
if ("serviceWorker" in navigator && location.protocol === "https:") {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/static/sw.js", {scope: "/"}).catch(e => {
      console.warn("SW register failed:", e);
    });
  });
}
