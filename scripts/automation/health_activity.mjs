import { execFileSync } from "node:child_process";
import { pathToFileURL } from "node:url";

const DAY_SECONDS = 86400;
const COMMIT_INTERVAL_DAYS = 15;
const ALERT_AFTER_DAYS = 18;
const TARGET_REPOSITORY = "Alexio00/HEALTH";
const TARGET_BRANCH = "scheduler";
const HEARTBEAT_JOB_NAME = "Approved scheduler SHA - heartbeat";
const API_ROOT = "https://api.github.com";

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

export async function latestSuccessfulHeartbeatRun({
  fetchImpl = fetch,
  token,
  acceptedMainSha,
}) {
  if (typeof token !== "string" || token.length < 20)
    throw new Error("GitHub Actions read token unavailable");
  if (typeof acceptedMainSha !== "string" || !/^[a-f0-9]{40}$/.test(acceptedMainSha))
    throw new Error("Accepted main SHA unavailable");

  const headers = {
    Accept: "application/vnd.github+json",
    Authorization: "Bearer " + token,
    "X-GitHub-Api-Version": "2022-11-28",
  };
  const runsUrl = API_ROOT + "/repos/" + TARGET_REPOSITORY +
    "/actions/workflows/health-activity.yml/runs?branch=main&event=schedule&per_page=100";
  const runsResponse = await fetchImpl(runsUrl, { headers });
  if (!runsResponse || runsResponse.ok !== true)
    throw new Error("GitHub scheduled workflow evidence unavailable");
  const runsPayload = await runsResponse.json();
  if (!runsPayload || !Array.isArray(runsPayload.workflow_runs))
    throw new Error("GitHub scheduled workflow evidence malformed");

  const runs = runsPayload.workflow_runs
    .filter((run) => run && run.event === "schedule" &&
      run.head_branch === "main" && run.head_sha === acceptedMainSha &&
      run.status === "completed" && Number.isSafeInteger(run.id) &&
      typeof run.created_at === "string" && Number.isFinite(Date.parse(run.created_at)))
    .sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at));

  for (const run of runs) {
    const jobsUrl = API_ROOT + "/repos/" + TARGET_REPOSITORY +
      "/actions/runs/" + run.id + "/jobs?per_page=100";
    const jobsResponse = await fetchImpl(jobsUrl, { headers });
    if (!jobsResponse || jobsResponse.ok !== true)
      throw new Error("GitHub heartbeat job evidence unavailable");
    const jobsPayload = await jobsResponse.json();
    if (!jobsPayload || !Array.isArray(jobsPayload.jobs))
      throw new Error("GitHub heartbeat job evidence malformed");
    const job = jobsPayload.jobs.find((item) =>
      item && item.name === HEARTBEAT_JOB_NAME &&
      item.status === "completed" && item.conclusion === "success" &&
      typeof item.completed_at === "string" &&
      Number.isFinite(Date.parse(item.completed_at)));
    if (job) return Math.floor(Date.parse(job.completed_at) / 1000);
  }
  return null;
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

function readHeartbeatCommit() {
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
    const now = Math.floor(Date.now() / 1000);
    const status = assessHeartbeat(readHeartbeatCommit(), now);
    console.log(formatStatus(status));
    if (mode === "heartbeat" && status.due) {
      writeHeartbeat();
      console.log("PASS: isolated scheduler branch heartbeat pushed");
    } else if (mode === "heartbeat") {
      console.log("PASS: not due; no commit");
    }
    if (mode === "check") {
      const lastRun = await latestSuccessfulHeartbeatRun({
        token: process.env.GITHUB_TOKEN,
        acceptedMainSha: process.env.GITHUB_SHA,
      });
      if (lastRun === null)
        throw new Error("HEALTH_HEARTBEAT_RUN_UNPROVEN: no successful accepted-main scheduled heartbeat job");
      const runStatus = assessHeartbeat(lastRun, now);
      console.log("last accepted-main heartbeat job: " + runStatus.ageDays.toFixed(2) + " days ago");
      if (runStatus.overdue)
        throw new Error("HEALTH_HEARTBEAT_RUN_STALE: last accepted-main scheduled heartbeat job exceeded 18 days");
    }
    // GitHub Actions failure notification is the email channel.
    // If both schedules are disabled, no in-repository watchdog can notify.
    if (status.overdue) throw new Error("HEALTH_SCHEDULER_OVERDUE: last heartbeat commit exceeded 18 days");
  } catch (error) {
    console.error(String(error.message || error));
    process.exitCode = 1;
  }
}
