/*
 * The student page, offline. Registered by /students only.
 *
 * It answers three kinds of request and lets everything else go to the network
 * untouched, so the staff and admin screens behave exactly as without it:
 *
 *   - /students itself: the network first, the copy kept from last time with no signal.
 *   - /api/v1/students/*: the same, so a routine read once is there offline.
 *     Not the free rooms, which go stale by the minute.
 *   - the built scripts, styles and images: kept, since a build never changes them.
 */

const VERSION = "v1";
const PAGE = `classtrack-page-${VERSION}`;
const DATA = `classtrack-data-${VERSION}`;
const FILES = `classtrack-files-${VERSION}`;
/** Files kept at most: each deploy brings new ones, and the old are never asked for again. */
const MAX_FILES = 300;

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(PAGE).then((cache) => cache.add("/students")).catch(() => {}));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter((k) => k.startsWith("classtrack-") && ![PAGE, DATA, FILES].includes(k))
            .map((k) => caches.delete(k)),
        ),
      )
      .then(() => self.clients.claim()),
  );
});

const isData = (url) =>
  url.pathname.startsWith("/api/v1/students/") && url.pathname !== "/api/v1/students/free-rooms";

const isFile = (url) =>
  url.pathname.startsWith("/_next/static/") ||
  url.pathname.startsWith("/icons/") ||
  url.pathname === "/diu-logo.png" ||
  // The logo, resized: only the site's own images, never a remote one.
  (url.pathname === "/_next/image" && (url.searchParams.get("url") ?? "").startsWith("/"));

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  if (request.mode === "navigate" && url.pathname === "/students") {
    // One page for every section: the section is in the address, read by the page.
    event.respondWith(networkFirst(request, PAGE, "/students"));
  } else if (isData(url)) {
    event.respondWith(networkFirst(request, DATA));
  } else if (isFile(url)) {
    event.respondWith(cacheFirst(request));
  }
});

async function networkFirst(request, name, key) {
  const cache = await caches.open(name);
  try {
    const response = await fetch(request);
    if (response.ok) await cache.put(key ?? request, response.clone());
    return response;
  } catch (error) {
    const kept = await cache.match(key ?? request);
    if (kept) return kept;
    throw error;
  }
}

async function cacheFirst(request) {
  const cache = await caches.open(FILES);
  const kept = await cache.match(request);
  if (kept) return kept;
  const response = await fetch(request);
  if (response.ok) {
    await cache.put(request, response.clone());
    trim(cache);
  }
  return response;
}

async function trim(cache) {
  const keys = await cache.keys();
  // Oldest first: delete from the front until within the limit.
  for (const key of keys.slice(0, Math.max(0, keys.length - MAX_FILES))) await cache.delete(key);
}

// The page lists the files it loaded before this worker was in charge of it,
// so they are kept too and the page opens offline the next time.
self.addEventListener("message", (event) => {
  if (event.data?.type !== "keep" || !Array.isArray(event.data.urls)) return;
  event.waitUntil(
    caches.open(FILES).then(async (cache) => {
      for (const href of event.data.urls) {
        try {
          const url = new URL(href, self.location.origin);
          if (url.origin === self.location.origin && isFile(url) && !(await cache.match(url))) {
            await cache.add(url);
          }
        } catch {
          /* one file not kept is not worth the rest */
        }
      }
      await trim(cache);
    }),
  );
});
