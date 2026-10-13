import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { join } from "node:path";
import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { pathToFileURL } from "node:url";
export const RUNTIME_FILES = [
  "index.html", "app.js", "styles.css", "vaccination.mjs", "supabase-client.js",
  "config.js", "manifest.webmanifest", "icon.svg", "sw.js",
  "oauth-home.html", "oauth-privacy.html", "oauth-test/consent.html",
  "oauth-test/consent.css", "oauth-test/consent.mjs", "oauth-test/consent-policy.mjs"
];
const SHELL_FILES = ["index.html", "styles.css", "app.js", "vaccination.mjs",
  "supabase-client.js", "config.js", "manifest.webmanifest", "icon.svg"];
export const digest = bytes => createHash("sha256").update(bytes).digest("hex");
export function build(source, out, sha) {
  if (!/^[0-9a-f]{40}$/.test(sha)) throw new Error("Invalid release SHA");
  const files = Object.fromEntries(RUNTIME_FILES.map(p => [p, readFileSync(join(source, p))]));
  const html = files["index.html"].toString();
  if (!html.includes("__HEALTH_RELEASE__")) throw new Error("Missing HTML release token");
  files["index.html"] = Buffer.from(html.replaceAll("__HEALTH_RELEASE__", sha)
    .replaceAll("__HEALTH_SHORT_RELEASE__", sha.slice(0, 8)));
  const hashes = Object.fromEntries(SHELL_FILES.map(p => ["./" + p, digest(files[p])]));
  const sw = files["sw.js"].toString();
  if (!sw.includes("__HEALTH_RELEASE__") || !sw.includes("/* __HEALTH_HASHES__ */ {}"))
    throw new Error("Missing SW release tokens");
  files["sw.js"] = Buffer.from(sw.replaceAll("__HEALTH_RELEASE__", sha)
    .replace("/* __HEALTH_HASHES__ */ {}", JSON.stringify(hashes)));
  for (const [p, bytes] of Object.entries(files)) {
    const target = join(out, p);
    mkdirSync(join(target, ".."), { recursive: true });
    writeFileSync(target, bytes);
  }
  const manifest = { schema: 1, sha, files: Object.fromEntries(
    Object.entries(files).map(([p, bytes]) => [p, digest(bytes)])) };
  writeFileSync(join(out, "release.json"), JSON.stringify(manifest, null, 2) + "\n");
  return manifest;
}
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const sha = process.env.GITHUB_SHA;
  if (process.env.GITHUB_REF !== "refs/heads/pwa" ||
      execFileSync("git", ["rev-parse", "HEAD"], { encoding: "utf8" }).trim() !== sha)
    throw new Error("Build must use exact checked-out pwa Actions SHA");
  console.log(build("frontend", process.argv[2], sha));
}
