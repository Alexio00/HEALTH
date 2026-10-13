import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";
const CONTROL = new Set([".github/workflows/deploy-pages.yml",
  ".github/workflows/code-validation.yml", ".github/workflows/pwa-scope.yml"]);
const DOCS = new Set(["AGENTS.md", "docs/PWA_RELEASE.md"]);
export function scopePolicy(entries, pr) {
  if (!entries.length) throw new Error("Empty PR scope");
  const controls = entries.filter(e => CONTROL.has(e.path) || e.path.startsWith("frontend/release/"));
  for (const e of entries) {
    if (e.mode !== "100644") throw new Error("Non-regular file: " + e.path);
    if (e.path.split("/").some(p => !p || p === "." || p === ".." || p.startsWith(".")) &&
        !CONTROL.has(e.path)) throw new Error("Unsafe path: " + e.path);
    if (!(e.path.startsWith("frontend/") || DOCS.has(e.path) || CONTROL.has(e.path)))
      throw new Error("Forbidden PWA path: " + e.path);
    if (/(^|\/)(records|sources|labs|private|secrets)(\/|\.)/i.test(e.path) ||
        /\.(sql|pem|key|env)$/i.test(e.path)) throw new Error("Private/backend path: " + e.path);
  }
  if (controls.length && !(pr.authorId === 308028794 &&
      pr.body.split(/\r?\n/).includes("PWA-RELEASE-CONTROL: " + pr.head)))
    throw new Error("Release controls require owner PR and exact head confirmation");
  return { paths: entries.length, releaseControls: controls.length };
}
function git(...args) { return execFileSync("git", args, { encoding: "utf8" }); }
export function checkGit(base, head, pr) {
  if (![base, head].every(x => /^[0-9a-f]{40}$/.test(x))) throw new Error("Invalid commit SHA");
  const paths = git("diff", "--no-renames", "--name-only", "-z", base, head).split("\0").filter(Boolean);
  const entries = paths.map(path => {
    const record = git("ls-tree", head, "--", path) || git("ls-tree", base, "--", path);
    return { path, mode: record.split(" ")[0] };
  });
  const result = scopePolicy(entries, pr);
  if (paths.includes(".github/workflows/code-validation.yml")) {
    const normalize = s => s.replace(/      - name: Frontend syntax and synthetic contract checks\n[\s\S]*?(?=      - name: Python syntax)/,
      "      # FRONTEND CHECK BLOCK\n");
    if (normalize(git("show", base + ":.github/workflows/code-validation.yml")) !==
        normalize(git("show", head + ":.github/workflows/code-validation.yml")))
      throw new Error("Writer/backend CI changes are forbidden in pwa");
  }
  return result;
}
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const event = JSON.parse(readFileSync(process.env.GITHUB_EVENT_PATH, "utf8"));
  const pr = event.pull_request;
  if (pr?.base.ref !== "pwa") throw new Error("Expected pwa PR");
  console.log(checkGit(pr.base.sha, pr.head.sha,
    { authorId: pr.user.id, body: pr.body || "", head: pr.head.sha }));
}
