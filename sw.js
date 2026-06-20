const CACHE_NAME = "diia-pwa-v7";

const APP_SHELL = [
  "/",
  "/app/docs",
  "/index.html",
  "/manifest.json",
  "/service-worker.js",
  "/sw.js",
  "/css/app.1f25d1c9.css",
  "/js/chunk-vendors.5ff6834c.js",
  "/js/app.68848094.js",
  "/fonts/e_ukraine_regular.otf",
  "/fonts/e_ukraine_medium.otf",
  "/fonts/e-Ukraine-Regular.otf",
  "/img/icons/android-chrome-192x192.png",
  "/img/icons/android-chrome-1080x2400.png",
  "/img/icons/apple-touch-icon-180x180.png",
  "/img/icons/DiiaLogo.png",
  "/img/icons/android-chrome-512x512.png",
  "/img/light_background.png",
  "/img/fingerprint.png",
  "/img/left-arrow.png",
  "/img/DS_arrowBack.svg",
  "/img/DS_settings.svg",
  "/photo.jpg",
  "/sign.png",
  "/demo_data.json"
];

const OFFLINE_API_RESPONSE = {
  status: "ok",
  code: "ok",
  offline: 1,
  version: "local-pwa"
};

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) =>
      Promise.all(
        APP_SHELL.map((url) =>
          cache.add(url).catch(() => undefined)
        )
      )
    )
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) =>
      Promise.all(
        cacheNames
          .filter((cacheName) => cacheName !== CACHE_NAME)
          .map((cacheName) => caches.delete(cacheName))
      )
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") {
    return;
  }

  const requestUrl = new URL(event.request.url);

  if (requestUrl.origin !== self.location.origin) {
    return;
  }

  if (event.request.mode === "navigate") {
    event.respondWith(networkFirst(event.request, "/index.html"));
    return;
  }

  if (requestUrl.pathname.startsWith("/api/")) {
    event.respondWith(networkFirst(event.request, null, apiFallback()));
    return;
  }

  event.respondWith(cacheFirst(event.request));
});

async function cacheFirst(request) {
  const cachedResponse = await caches.match(request);

  if (cachedResponse) {
    return cachedResponse;
  }

  const networkResponse = await fetch(request);
  await putInCache(request, networkResponse.clone());
  return networkResponse;
}

async function networkFirst(request, fallbackUrl, fallbackResponse) {
  try {
    const networkResponse = await fetch(request);
    await putInCache(request, networkResponse.clone());
    return networkResponse;
  } catch (error) {
    const cachedResponse = await caches.match(request);

    if (cachedResponse) {
      return cachedResponse;
    }

    if (fallbackUrl) {
      const fallback = await caches.match(fallbackUrl);
      if (fallback) {
        return fallback;
      }
    }

    if (fallbackResponse) {
      return fallbackResponse;
    }

    throw error;
  }
}

async function putInCache(request, response) {
  if (!response || response.status >= 400) {
    return;
  }

  const cache = await caches.open(CACHE_NAME);
  await cache.put(request, response);
}

function apiFallback() {
  return new Response(JSON.stringify(OFFLINE_API_RESPONSE), {
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": "no-store"
    }
  });
}
