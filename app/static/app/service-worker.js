/* Service worker: cache the PWA shell so the app loads when briefly offline.
   Real-time alert data is never cached; dynamic API calls go to the network. */

const CACHE_NAME = "elderly-care-v1";
const APP_SHELL = [
  "/app",
  "/static/app/styles.css",
  "/static/app/app.js",
  "/static/app/icon-192.png",
  "/static/app/icon-512.png",
  "/manifest.json",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);

  // Never go to cache for API calls (alerts/statistics are live data).
  if (url.pathname.startsWith("/api/")) {
    return; // let the network/browser handle it
  }

  // For app shell assets: try network first, fall back to cache (offline shell).
  event.respondWith(
    caches.match(event.request).then((cached) => {
      if (cached) return cached;
      return fetch(event.request)
        .then((res) => {
          if (res.ok && url.origin === location.origin) {
            const clone = res.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
          }
          return res;
        })
        .catch(() => caches.match("/app"));
    })
  );
});
