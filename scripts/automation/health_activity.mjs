import { execFileSync } from "node:child_process";
import { pathToFileURL } from "node:url";

const DAY_SECONDS = 86400;
const COMMIT_INTERVAL_DAYS = 15;
const ALERT_AFTER_DAYS = 18;
const TARGET_REPOSITORY = "Alexio00/HEALTH";
const TARGET_BRANCH = "scheduler";

export function assessHeartbeat(lastCommitSeconds, nowSeconds) {
  if (![lastCommitSeconds, nowSeconds].every(Number.isSafeInteger) || lastCommitSeconds <= 0)
    throw new Error("Invalid commit timestamps");
  const elapsed = nowSeconds - lastCommitSeconds;
  if (elapsed < -300) throw new Error("Future commit timestamp");
  const days = Math.max(0, elapsed / DAY_SECONDS);
  return {
    ageDays: days,
    due: elapsed >= COMMIT_INTERVAL_DAYS * DAY_SECONDS,
    overdue: elapsed >= ALERT_AFTER_DAYS * DAY_SECONDS,
  };
}

function git(args, { capture = false } = {}) {
  const output = execFileSync("git", args, {
    encoding: "utf8",
    stdio: capture ? ["ignore", "pipe", "pipe"] : "inherit",
  });
  return capture ? output.trim() : "";
}

function ensureTrustedEvent() {
  const env = process.env;
  if (env.GITHUB_ACTIONS !== "true" ||
      env.GITHUB_REPOSITORY !== TARGET_REPOSITORY ||
      env.GITHUB_REF !== "refs/heads/main" ||
      !["schedule", "workflow_dispatch"].includes(env.GITHUB_EVENT_NAME))
    throw new Error("Refuse execution outside approved HEALTH main Actions");
}

function readHeartbeat() {
  git(["fetch", "--no-tags", "origin",
    "refs/heads/" + TARGET_BRANCH + ":refs/remotes/origin/" + TARGET_BRANCH]);
  const raw = git(["log", "-1", "--format=%ct",
    "refs/remotes/origin/" + TARGET_BRANCH], { capture: true });
  const seconds = Number(raw);
  if (!Number.isSafeInteger(seconds)) throw new Error("Invalid heartbeat timestamp");
  return seconds;
}

export function formatStatus(status) {
  return "scheduler branch: " + status.ageDays.toFixed(2) +
    " days; due=" + status.due + "; overdue=" + status.overdue;
}

function writeHeartbeat() {
  git(["switch", "-C", TARGET_BRANCH, "refs/remotes/origin/" + TARGET_BRANCH]);
  git(["-c", "user.name=github-actions[bot]",
    "-c", "user.email=41898282+github-actions[bot]@users.noreply.github.com",
    "commit", "--allow-empty", "-m", "chore(scheduler): scheduled 15-day heartbeat"]);
  // Explicit destination: never push to main, pwa or another ref.
  git(["push", "origin", "HEAD:refs/heads/" + TARGET_BRANCH]);
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  try {
    ensureTrustedEvent();
    const mode = process.argv[2];
    if (!["heartbeat", "check"].includes(mode)) throw new Error("Unknown mode");
    const last = readHeartbeat();
    const status = assessHeartbeat(last, Math.floor(Date.now() / 1000));
    console.log(formatStatus(status));
    if (mode === "heartbeat" && status.due) {
      writeHeartbeat();
      console.log("PASS: isolated scheduler branch heartbeat pushed");
    } else if (mode === "heartbeat") {
      console.log("PASS: not due; no commit");
    }
    // GitHub Actions failure notification is the email channel.
    // A completely disabled schedule cannot notify from inside itself.
    if (status.overdue) throw new Error("HEALTH_SCHEDULER_OVERDUE: last heartbeat exceeded 18 days");
  } catch (error) {
    console.error(String(error.message || error));
    process.exitCode = 1;
  }
}
