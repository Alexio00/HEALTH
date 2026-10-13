const RELEASE = "__HEALTH_RELEASE__";
const FILE_HASHES = /* __HEALTH_HASHES__ */ {};
const CACHE = "health-shell-" + RELEASE;
const SHELL = ["./index.html", "./styles.css", "./app.js", "./vaccination.mjs",
  "./supabase-client.js", "./config.js", "./manifest.webmanifest", "./icon.svg"];
const BASE = new URL("./", self.location.href);
const STATIC = new Set(SHELL.map(path => new URL(path, BASE).href));

function cacheKey(request) {
  const url = new URL(request.url);
  if (request.method !== "GET" || url.origin !== BASE.origin || url.search ||
      request.headers.has("authorization") || request.headers.has("range")) return null;
  url.hash = "";
  if (url.href === BASE.href) url.pathname += "index.html";
  return STATIC.has(url.href) ? url.href : null;
}

function safeResponse(response, key) {
  if (response.status !== 200 || response.redirected || response.type === "opaque" ||
      (response.url && response.url !== key)) return false;
  const control = response.headers.get("cache-control") || "";
  const vary = response.headers.get("vary") || "";
  if (/\b(no-store|private|no-cache)\b/i.test(control) || /(?:\*|authorization|cookie)/i.test(vary)) return false;
  const mime = (response.headers.get("content-type") || "").split(";")[0].trim();
  if (key.endsWith(".html")) return mime === "text/html";
  if (/\.(js|mjs)$/.test(key)) return /^(text|application)\/javascript$/.test(mime);
  if (key.endsWith(".css")) return mime === "text/css";
  if (key.endsWith(".webmanifest")) return /^(application\/manifest\+json|application\/json)$/.test(mime);
  if (key.endsWith(".svg")) return mime === "image/svg+xml";
  return false;
}

async function verifiedResponse(response, key) {
  if (!safeResponse(response, key)) return false;
  const relative = "./" + new URL(key).pathname.slice(BASE.pathname.length);
  const expected = FILE_HASHES[relative];
  if (!expected) return !/^[0-9a-f]{40}$/.test(RELEASE) && Object.keys(FILE_HASHES).length === 0; // local synthetic/dev source only
  const bytes = await response.clone().arrayBuffer();
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  const actual = Array.from(new Uint8Array(digest), b => b.toString(16).padStart(2, "0")).join("");
  return actual === expected;
}

self.addEventListener("install", event => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE);
    const fetched = [];
    for (const path of SHELL) {
      const key = new URL(path, BASE).href;
      const response = await fetch(key, { cache: "reload", credentials: "omit", redirect: "error" });
      if (!await verifiedResponse(response, key)) throw new Error("Unsafe or mismatched shell response");
      fetched.push([key, response]);
    }
    for (const [key, response] of fetched) await cache.put(key, response);
    await self.skipWaiting();
  })());
});

self.addEventListener("activate", event => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.filter(k => k.startsWith("health-shell-") && k !== CACHE).map(k => caches.delete(k)));
    await self.clients.claim();
  })());
});

self.addEventListener("fetch", event => {
  const key = cacheKey(event.request);
  if (!key) return;
  event.respondWith((async () => {
    const cache = await caches.open(CACHE);
    // A built worker serves one complete release; a new install changes CACHE.
    const existing = await cache.match(key);
    if (existing && FILE_HASHES["./" + new URL(key).pathname.slice(BASE.pathname.length)]) return existing;
    try {
      const response = await fetch(key, { credentials: "omit", redirect: "error" });
      if (!await verifiedResponse(response, key)) throw new Error("Release response rejected");
      await cache.put(key, response.clone());
      return response;
    } catch (error) {
      const cached = await cache.match(key);
      if (cached) return cached;
      throw error;
    }
  })());
});
