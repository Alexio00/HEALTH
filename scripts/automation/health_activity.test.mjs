import assert from "node:assert/strict";
import { test } from "node:test";
import { assessHeartbeat, formatStatus } from "./health_activity.mjs";

const DAY = 86400;
const NOW = 1780000000;
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
console.log("PASS: synthetic 15/18 day boundary, stale detection and timestamp rejection");
