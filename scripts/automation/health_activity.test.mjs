import assert from "node:assert/strict";
import { test } from "node:test";
import {
  assessHeartbeat,
  formatStatus,
  latestSuccessfulHeartbeatRun,
} from "./health_activity.mjs";

const DAY = 86400;
const NOW = 1780000000;
const MAIN_SHA = "a".repeat(40);
function atAge(ageDays) {
  return assessHeartbeat(NOW - Math.round(ageDays * DAY), NOW);
}

test("fresh and 14-day heartbeats must not write", () => {
  for (const days of [0, 1, 14, 14.99]) {
    assert.equal(atAge(days).due, false);
    assert.equal(atAge(days).overdue, false);
  }
});
test("15-day heartbeat is due and below failure threshold", () => {
  assert.deepEqual([atAge(15).due, atAge(15).overdue], [true, false]);
  assert.deepEqual([atAge(17).due, atAge(17).overdue], [true, false]);
});
test("18-day stale heartbeat triggers email-compatible failure", () => {
  assert.equal(atAge(18).overdue, true);
  assert.equal(atAge(35).overdue, true);
  assert.match(formatStatus(atAge(19)), /overdue=true/);
});
test("bad and future timestamps fail closed", () => {
  for (const timestamp of [NaN, 0, Infinity, -10, 3.2])
    assert.throws(() => assessHeartbeat(timestamp, NOW));
  assert.throws(() => assessHeartbeat(NOW + 301, NOW));
  assert.equal(assessHeartbeat(NOW + 300, NOW).due, false);
});

function fakeFetch(runs, jobsByRun, options = {}) {
  return async (url, init) => {
    assert.match(init.headers.Authorization, /^Bearer [A-Za-z0-9_-]{20,}$/);
    if (url.includes("/actions/workflows/health-activity.yml/runs?")) {
      if (options.runsStatus) return { ok: false, status: options.runsStatus, json: async () => ({}) };
      return { ok: true, json: async () => ({ workflow_runs: runs }) };
    }
    const match = url.match(/\/actions\/runs\/(\d+)\/jobs\?/);
    assert.ok(match, "only the fixed workflow-runs and run-jobs endpoints are allowed");
    if (options.jobsStatus) return { ok: false, status: options.jobsStatus, json: async () => ({}) };
    return { ok: true, json: async () => ({ jobs: jobsByRun[Number(match[1])] || [] }) };
  };
}

function run(id, overrides = {}) {
  return {
    id, event: "schedule", head_branch: "main", head_sha: MAIN_SHA,
    status: "completed", conclusion: "failure",
    created_at: "2026-10-17T05:17:00Z",
    ...overrides,
  };
}
function job(conclusion = "success", completed_at = "2026-10-17T05:18:00Z") {
  return {
    name: "Approved scheduler SHA - heartbeat",
    status: "completed", conclusion, completed_at,
  };
}

test("real successful heartbeat job is recognized even if watchdog made overall run fail", async () => {
  const fetchImpl = fakeFetch([run(11)], { 11: [job()] });
  const result = await latestSuccessfulHeartbeatRun({
    fetchImpl, token: "x".repeat(24), acceptedMainSha: MAIN_SHA,
  });
  assert.equal(result, Math.floor(Date.parse("2026-10-17T05:18:00Z") / 1000));
});

test("manual runs, non-main runs, and other accepted SHAs cannot prove scheduled heartbeat", async () => {
  const runs = [
    run(12, { event: "workflow_dispatch" }),
    run(13, { head_branch: "scheduler" }),
    run(14, { head_sha: "b".repeat(40) }),
  ];
  const result = await latestSuccessfulHeartbeatRun({
    fetchImpl: fakeFetch(runs, { 12: [job()], 13: [job()], 14: [job()] }),
    token: "x".repeat(24), acceptedMainSha: MAIN_SHA,
  });
  assert.equal(result, null);
});

test("a successful workflow without a successful heartbeat job is not evidence", async () => {
  const result = await latestSuccessfulHeartbeatRun({
    fetchImpl: fakeFetch([run(15, { conclusion: "success" })], { 15: [job("skipped")] }),
    token: "x".repeat(24), acceptedMainSha: MAIN_SHA,
  });
  assert.equal(result, null);
});

test("missing token, bad SHA, and API failures fail closed", async () => {
  await assert.rejects(() => latestSuccessfulHeartbeatRun({
    fetchImpl: fakeFetch([], {}), token: "", acceptedMainSha: MAIN_SHA,
  }), /token unavailable/);
  await assert.rejects(() => latestSuccessfulHeartbeatRun({
    fetchImpl: fakeFetch([], {}), token: "x".repeat(24), acceptedMainSha: "bad",
  }), /Accepted main SHA unavailable/);
  await assert.rejects(() => latestSuccessfulHeartbeatRun({
    fetchImpl: fakeFetch([], {}, { runsStatus: 403 }), token: "x".repeat(24), acceptedMainSha: MAIN_SHA,
  }), /workflow evidence unavailable/);
  await assert.rejects(() => latestSuccessfulHeartbeatRun({
    fetchImpl: fakeFetch([run(16)], {}, { jobsStatus: 403 }), token: "x".repeat(24), acceptedMainSha: MAIN_SHA,
  }), /job evidence unavailable/);
});
console.log("PASS: heartbeat freshness plus authenticated accepted-main workflow-run evidence");
