import { createHash } from "node:crypto";
import { pathToFileURL } from "node:url";
import { RUNTIME_FILES } from "./build.mjs";
const hash = bytes => createHash("sha256").update(bytes).digest("hex");
export function validateMarker(marker, sha) {
  if (marker.schema !== 1 || marker.sha !== sha) throw new Error("Published release SHA mismatch");
  const keys = Object.keys(marker.files || {}).sort();
  if (JSON.stringify(keys) !== JSON.stringify([...RUNTIME_FILES].sort()) ||
      Object.values(marker.files).some(x => !/^[a-f0-9]{64}$/.test(x)))
    throw new Error("Invalid release file manifest");
}
function mimeFor(path, mime) {
  mime = mime.split(";")[0].trim();
  if (path.endsWith(".html")) return mime === "text/html";
  if (/\.(js|mjs)$/.test(path)) return /^(text|application)\/javascript$/.test(mime);
  if (path.endsWith(".css")) return mime === "text/css";
  if (path.endsWith(".svg")) return mime === "image/svg+xml";
  return /^(application\/json|application\/manifest\+json)$/.test(mime);
}
export async function probe(base, sha, fetcher = fetch) {
  if (!/^[0-9a-f]{40}$/.test(sha)) throw new Error("Invalid expected SHA");
  async function read(path) {
    const response = await fetcher(new URL(path, base), {
      redirect: "error", cache: "no-store", signal: AbortSignal.timeout(10000)
    });
    if (response.status !== 200 || response.redirected ||
        !mimeFor(path || "index.html", response.headers.get("content-type") || ""))
      throw new Error("HTTP/MIME failure: " + path);
    return Buffer.from(await response.arrayBuffer());
  }
  const marker = JSON.parse((await read("release.json")).toString());
  validateMarker(marker, sha);
  const results = await Promise.all(RUNTIME_FILES.map(async path => {
    if (hash(await read(path)) !== marker.files[path]) throw new Error("Published bytes mismatch: " + path);
    return path;
  }));
  if (hash(await read("")) !== marker.files["index.html"]) throw new Error("Root HTML mismatch");
  return { sha, files: results.length, root: "PASS" };
}
export async function retryProbe(run, { attempts = 12, delayMs = 10000, wait = ms => new Promise(r => setTimeout(r, ms)) } = {}) {
  for (let attempt = 1; attempt <= attempts; attempt++) {
    try { return await run(); } catch (error) {
      if (attempt === attempts) throw error;
      console.log("Pages not ready; bounded retry " + attempt + ": " + error.message);
      await wait(delayMs);
    }
  }
}
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  if (process.env.GITHUB_REF !== "refs/heads/pwa") throw new Error("Expected pwa");
  console.log(await retryProbe(() => probe("https://alexio00.github.io/HEALTH/", process.env.GITHUB_SHA)));
}
