// Service Worker for Hanmir Smart Helmet PWA
const CACHE_NAME = "hanmir-safety-v1";
const STATIC_ASSETS = [
  "/",
  "/index.html",
  "/manifest.webmanifest",
  "/icons/icon-192.svg",
  "/icons/icon-512.svg"
];

self.addEventListener("install", event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      return cache.addAll(STATIC_ASSETS);
    })
  );
  self.skipWaiting();
});

self.addEventListener("activate", event => {
  event.waitUntil(
    caches.keys().then(keys => {
      return Promise.all(
        keys.map(key => {
          if (key !== CACHE_NAME) {
            return caches.delete(key);
          }
        })
      );
    })
  );
  self.clients.claim();
});

// Network-first for API & WS, Cache-first for static assets
self.addEventListener("fetch", event => {
  const url = new URL(event.request.url);

  // Skip caching for API, WebSockets, or camera streams
  if (
    url.pathname.startsWith("/api") ||
    url.pathname.startsWith("/ws") ||
    url.pathname.startsWith("/captures") ||
    event.request.method !== "GET"
  ) {
    return;
  }

  event.respondWith(
    fetch(event.request)
      .then(response => {
        // Clone response to put into cache
        if (response.status === 200) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then(cache => {
            cache.put(event.request, clone);
          });
        }
        return response;
      })
      .catch(async () => {
        // Fallback to cache on network failure
        const cached = await caches.match(event.request);
        if (cached) return cached;
        if (event.request.mode === "navigate") {
          return caches.match("/index.html");
        }
        return new Response("Offline", { status: 503, statusText: "Offline" });
      })
  );
});
