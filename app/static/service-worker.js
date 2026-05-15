const CACHE_NAME = "personal-ai-assistant-shell-v12";

const SHELL_ASSETS = [
  "/",
  "/manifest.webmanifest",
  "/static/app.js?v=prod-20260514-2",
  "/static/styles.css",
  "/static/icons/icon-192.png",
  "/static/icons/icon-512.png",
  "/static/icons/icon.svg",
];

const API_PREFIXES = [
  "/brief",
  "/llm",
  "/preferences",
  "/schedule",
  "/status",
  "/tts",
  "/notifications",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(SHELL_ASSETS)),
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))),
      )
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") {
    return;
  }

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) {
    return;
  }

  if (API_PREFIXES.some((prefix) => url.pathname.startsWith(prefix))) {
    return;
  }

  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request)
        .then((response) => {
          const copy = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put("/", copy));
          return response;
        })
        .catch(() => caches.match("/")),
    );
    return;
  }

  if (url.pathname.startsWith("/static") || SHELL_ASSETS.includes(url.pathname)) {
    event.respondWith(
      caches.match(request).then((cached) => {
        return fetch(request)
          .then((response) => {
            const copy = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
            return response;
          })
          .catch(() => cached);
      }),
    );
  }
});

self.addEventListener("push", (event) => {
  let payload = {};
  if (event.data) {
    try {
      payload = event.data.json();
    } catch {
      payload = { body: event.data.text() };
    }
  }

  const title = payload.title || "Personal AI Assistant";
  const options = {
    body: payload.body || "New update available.",
    icon: "/static/icons/icon-192.png",
    badge: "/static/icons/icon-192.png",
    tag: payload.tag || "personal-ai-assistant",
    data: {
      url: payload.url || "/",
    },
  };

  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const targetUrl = new URL(event.notification.data?.url || "/", self.location.origin).href;

  event.waitUntil(
    self.clients
      .matchAll({ type: "window", includeUncontrolled: true })
      .then((clientList) => {
        for (const client of clientList) {
          const clientUrl = new URL(client.url);
          if (clientUrl.origin === self.location.origin) {
            if ("navigate" in client) {
              client.navigate(targetUrl);
            }
            return client.focus();
          }
        }
        return self.clients.openWindow(targetUrl);
      }),
  );
});
