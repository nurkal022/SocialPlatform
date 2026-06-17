// Ұстаз — minimal service worker. Caches static + last-visited pages for offline shell.

const CACHE = "ustaz-v1";
const STATIC_ASSETS = [
  "/static/css/app.css",
  "/static/js/app.js",
  "/static/img/favicon.svg",
  "/static/manifest.json",
];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(STATIC_ASSETS)));
  self.skipWaiting();
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);

  // Never cache API/streaming/admin/auth endpoints
  if (
    url.pathname.startsWith("/ai/") ||
    url.pathname.startsWith("/admin/") ||
    url.pathname.startsWith("/accounts/") ||
    url.pathname.includes("/submit/") ||
    url.pathname.includes("/complete/") ||
    url.pathname === "/healthz"
  ) return;

  // Static: cache-first
  if (url.pathname.startsWith("/static/") || url.pathname.startsWith("/media/")) {
    e.respondWith(
      caches.match(req).then((cached) =>
        cached || fetch(req).then((resp) => {
          if (resp.ok) caches.open(CACHE).then((c) => c.put(req, resp.clone()));
          return resp;
        })
      )
    );
    return;
  }

  // HTML: network-first, fall back to cache for offline shell
  if (req.headers.get("accept") && req.headers.get("accept").includes("text/html")) {
    e.respondWith(
      fetch(req)
        .then((resp) => {
          if (resp.ok) {
            const copy = resp.clone();
            caches.open(CACHE).then((c) => c.put(req, copy));
          }
          return resp;
        })
        .catch(() => caches.match(req) || caches.match("/"))
    );
  }
});
