import test from 'node:test';
import assert from 'node:assert/strict';
import { ConsentPolicyBlocked, evaluateBrowserConsent, nonceHash } from './browser_consent_policy.mjs';

const U1 = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';
const U2 = 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb';
const SID = 'cccccccc-cccc-4ccc-8ccc-cccccccccccc';
const CHID = 'dddddddd-dddd-4ddd-8ddd-dddddddddddd';
const NONCE = 'e'.repeat(64);
const KEY = 'writer-' + '0'.repeat(32);
const SHA = '1'.repeat(40);
const DIGEST = '2'.repeat(64);
const BEFORE = '3'.repeat(64);
const AFTER = '4'.repeat(64);
const REVIEW = '5'.repeat(64);
const NOW = 2_000_000;

async function fixture() {
  const challenge = {
    challenge_id: CHID, request_key: KEY, kind: 'candidate',
    owner_uid: U1, session_id: SID,
    candidate_sha: DIGEST, before_sha: BEFORE, after_sha: AFTER,
    review_sha: REVIEW, accepted_sha: SHA, nonce_sha: await nonceHash(NONCE),
    issued_at_ms: NOW - 20_000, expires_at_ms: NOW + 20_000, state: 'PENDING'
  };
  const verified = {
    owner_uid: U1, session_id: SID, jwt_verified: true,
    session_live: true, owner_allowlisted: true, origin_verified: true,
    csrf_verified: true
  };
  const observed = {
    request_key: KEY, candidate_sha: DIGEST, before_sha: BEFORE,
    after_sha: AFTER, review_sha: REVIEW, accepted_sha: SHA,
    state: 'PREPARED'
  };
  const answer = {
    challenge_id: CHID, nonce: NONCE, displayed_review_sha: REVIEW,
    decision: 'confirm'
  };
  return { challenge, verified, observed, answer, nowMs: NOW };
}
async function denied(mutator, code) {
  const x = await fixture();
  mutator(x);
  await assert.rejects(() => evaluateBrowserConsent(x), e =>
    e instanceof ConsentPolicyBlocked && (!code || e.code === code));
}

test('confirmation matches only: result is not a signed approval', async () => {
  const result = await evaluateBrowserConsent(await fixture());
  assert.deepEqual(result, {
    outcome: 'POLICY_MATCH_ONLY', challenge_id: CHID,
    request_key: KEY, candidate_sha: DIGEST, decision: 'confirm'
  });
  assert.equal(Object.isFrozen(result), true);
  assert.equal(Object.hasOwn(result, 'approved'), false);
  assert.equal(Object.hasOwn(result, 'receipt'), false);
  assert.equal(Object.hasOwn(result, 'owner_uid'), false);
  assert.equal(Object.hasOwn(result, 'session_id'), false);
});

test('explicit decline is NOT authorization or automatic Writer rollback', async () => {
  const x = await fixture(); x.answer.decision = 'decline';
  const value = await evaluateBrowserConsent(x);
  assert.equal(value.decision, 'decline');
  assert.equal(value.outcome, 'POLICY_MATCH_ONLY');
});

test('missing or extraneous browser fields fail closed', async () => {
  await denied(x => delete x.answer.nonce, 'browser_answer_shape');
  await denied(x => { x.answer.body_text = 'synthetic'; }, 'browser_answer_shape');
  await denied(x => { x.answer.secret = 'synthetic'; }, 'browser_answer_shape');
  await denied(x => { x.answer = []; }, 'browser_answer_shape');
  await denied(x => { x.answer = null; }, 'browser_answer_shape');
});

test('browser cannot provide independent Auth or Writer evidence', async () => {
  await denied(x => { x.verified = { ...x.verified, body_text: 'synthetic' }; }, 'trusted_context_shape');
  await denied(x => { x.observed = { ...x.observed, actor: 'owner' }; }, 'writer_readback_shape');
  await denied(x => { x.challenge = { ...x.challenge, extra: 'false' }; }, 'challenge_shape');
  await denied(x => { x.verified = []; }, 'trusted_context_shape');
  await denied(x => { x.observed = 'ready'; }, 'writer_readback_shape');
});

test('Auth requires verified JWT, active session, owner allowlist, Origin and CSRF', async () => {
  for (const field of ['jwt_verified','session_live','owner_allowlisted',
                        'origin_verified','csrf_verified']) {
    for (const value of [false, 1, 'true', null, {}, []]) {
      await denied(x => { x.verified[field] = value; }, 'verified_server_evidence_required');
    }
  }
});

test('foreign owner and foreign session are blocked', async () => {
  await denied(x => { x.verified.owner_uid = U2; }, 'owner_session_mismatch');
  await denied(x => { x.verified.session_id = U2; }, 'owner_session_mismatch');
  await denied(x => { x.challenge.owner_uid = U2; }, 'owner_session_mismatch');
});

test('nonce is not a URL-only bearer: wrong nonce is denied', async () => {
  await denied(x => { x.answer.nonce = 'f'.repeat(64); }, 'nonce_mismatch');
  await denied(x => { x.answer.nonce = NONCE.toUpperCase(); }, 'answer_nonce_invalid');
  await denied(x => { x.answer.nonce = null; }, 'answer_nonce_invalid');
});

test('challenge id and displayed review digest must bind exactly', async () => {
  await denied(x => { x.answer.challenge_id = U2; }, 'challenge_mismatch');
  await denied(x => { x.answer.displayed_review_sha = '6'.repeat(64); }, 'displayed_review_mismatch');
  await denied(x => { x.answer.decision = 'auto-confirm'; }, 'answer_decision_invalid');
  await denied(x => { x.challenge.kind = 'intent'; }, 'unapproved_consent_kind');
});

test('candidate revision, before/after, review and accepted code SHA cannot drift', async () => {
  for (const field of ['candidate_sha','before_sha','after_sha','review_sha']) {
    await denied(x => { x.observed[field] = '7'.repeat(64); }, 'stale_or_changed_candidate');
  }
  await denied(x => { x.observed.accepted_sha = '8'.repeat(40); }, 'stale_or_changed_candidate');
  await denied(x => { x.observed.request_key = 'writer-' + 'f'.repeat(32); }, 'stale_or_changed_candidate');
  await denied(x => { x.observed.state = 'FINALIZED'; }, 'writer_operation_not_prepared');
});

test('challenge already consumed, declined or cancelled is not reusable', async () => {
  for (const state of ['CONSUMED','APPROVED','DECLINED','CANCELLED','FAILED']) {
    await denied(x => { x.challenge.state = state; }, 'challenge_not_pending');
  }
});

test('expiry and issue times are strict (5 min max)', async () => {
  await denied(x => { x.nowMs = x.challenge.expires_at_ms; }, 'challenge_expired');
  await denied(x => { x.nowMs = x.challenge.issued_at_ms - 1; }, 'challenge_expired');
  await denied(x => { x.challenge.expires_at_ms = x.challenge.issued_at_ms + 300001; }, 'challenge_ttl_invalid');
  await denied(x => { x.challenge.expires_at_ms = x.challenge.issued_at_ms; }, 'challenge_ttl_invalid');
  await denied(x => { x.nowMs = 'later'; }, 'trusted_clock_invalid');
  await denied(x => { x.nowMs = Number.NaN; }, 'trusted_clock_invalid');
});

test('malformed digests, release SHA, UID and opaque keys are rejected', async () => {
  await denied(x => { x.challenge.accepted_sha = 'x'.repeat(40); }, 'challenge_release_invalid');
  await denied(x => { x.challenge.candidate_sha = 'X'.repeat(64); }, 'challenge_digest_invalid');
  await denied(x => { x.challenge.owner_uid = 'email@example.com'; }, 'owner_uid_invalid');
  await denied(x => { x.challenge.request_key = 'REC-20261014-001'; }, 'request_key_invalid');
  await denied(x => { x.observed.candidate_sha = null; }, 'writer_digest_invalid');
});

test('pending consent cannot be forged by JSON getter or prototype object', async () => {
  await denied(x => { x.answer = Object.create(null); }, 'browser_answer_shape');
  await denied(x => {
    Object.defineProperty(x.answer, 'nonce', { enumerable: true, get() { return NONCE; } });
  }, 'browser_answer_shape');
});

test('non-enumerable and symbol fields cannot pass the boundary', async () => {
  await denied(x => {
    Object.defineProperty(x.answer, 'hidden', { value: 'synthetic', enumerable: false });
  }, 'browser_answer_shape');
  await denied(x => { x.verified[Symbol('hidden')] = 'synthetic'; }, 'trusted_context_shape');
});

test('missing private evidence returns denial, not throw of unhandled TypeError', async () => {
  for (const key of ['challenge','observed','verified','answer']) {
    await denied(x => { x[key] = undefined; });
  }
});


test('deterministic 4096 synthetic adversarial mutations fail closed', async () => {
  const mutations = [
    x => { x.challenge.request_key = 'REC-20261014-001'; },
    x => { x.challenge.kind = 'intent'; },
    x => { x.challenge.state = 'CONSUMED'; },
    x => { x.challenge.owner_uid = U2; },
    x => { x.challenge.session_id = U2; },
    x => { x.challenge.candidate_sha = '0'.repeat(64); },
    x => { x.challenge.before_sha = '0'.repeat(64); },
    x => { x.challenge.after_sha = '0'.repeat(64); },
    x => { x.challenge.review_sha = '0'.repeat(64); },
    x => { x.challenge.accepted_sha = '0'.repeat(40); },
    x => { x.challenge.nonce_sha = '0'.repeat(64); },
    x => { x.challenge.expires_at_ms = NOW - 1; },
    x => { x.nowMs = NOW + 5 * 60 * 1000; },
    x => { x.verified.owner_uid = U2; },
    x => { x.verified.session_id = U2; },
    x => { x.verified.jwt_verified = false; },
    x => { x.verified.session_live = false; },
    x => { x.verified.owner_allowlisted = 'true'; },
    x => { x.verified.origin_verified = false; },
    x => { x.verified.csrf_verified = false; },
    x => { x.observed.request_key = 'writer-' + '9'.repeat(32); },
    x => { x.observed.candidate_sha = '9'.repeat(64); },
    x => { x.observed.before_sha = '9'.repeat(64); },
    x => { x.observed.after_sha = '9'.repeat(64); },
    x => { x.observed.review_sha = '9'.repeat(64); },
    x => { x.observed.accepted_sha = '9'.repeat(40); },
    x => { x.observed.state = 'VALIDATED'; },
    x => { x.answer.challenge_id = U2; },
    x => { x.answer.nonce = '9'.repeat(64); },
    x => { x.answer.displayed_review_sha = '9'.repeat(64); },
    x => { x.answer.decision = 'confirm-and-publish'; },
    x => { x.answer.owner_uid = U1; },
  ];
  let denied = 0;
  for (let i = 0; i < 4096; i++) {
    const x = await fixture();
    mutations[i % mutations.length](x);
    await assert.rejects(() => evaluateBrowserConsent(x),
      e => e instanceof ConsentPolicyBlocked);
    denied++;
  }
  assert.equal(denied, 4096);
});

// Independent audit B-01 / R-02: negative regressions, fixed outcome only.
test('B-01: concurrent answer mutation cannot alter captured decision', async () => {
  const x = await fixture();
  x.answer.decision = 'decline';
  const pending = evaluateBrowserConsent(x);
  x.answer.decision = 'confirm';
  const result = await pending;
  assert.equal(result.decision, 'decline');
});

test('B-01: invalid writer readback cannot become valid while digest is pending', async () => {
  const x = await fixture();
  x.observed.candidate_sha = '9'.repeat(64);
  const pending = evaluateBrowserConsent(x);
  x.observed.candidate_sha = DIGEST;
  await assert.rejects(pending, e => e instanceof ConsentPolicyBlocked && e.code === 'stale_or_changed_candidate');
});

test('B-01: shared candidate/owner mutation cannot modify snapshot or returned digest', async () => {
  const x = await fixture();
  const pending = evaluateBrowserConsent(x);
  x.challenge.candidate_sha = '9'.repeat(64);
  x.observed.candidate_sha = '9'.repeat(64);
  x.challenge.owner_uid = U2;
  x.verified.owner_uid = U2;
  x.challenge.request_key = 'writer-' + '9'.repeat(32);
  x.observed.request_key = x.challenge.request_key;
  const result = await pending;
  assert.equal(result.candidate_sha, DIGEST);
  assert.equal(result.request_key, KEY);
});

test('R-02: Proxy with inconsistent descriptor/get nonce is rejected', async () => {
  const x = await fixture();
  const target = x.answer;
  x.answer = new Proxy(target, {
    get(t, key, receiver) {
      if (key === 'nonce') return NONCE;
      return Reflect.get(t, key, receiver);
    },
    getOwnPropertyDescriptor(t, key) {
      if (key === 'nonce') return { configurable: true, enumerable: true, writable: true, value: 'f'.repeat(64) };
      return Reflect.getOwnPropertyDescriptor(t, key);
    },
  });
  await assert.rejects(() => evaluateBrowserConsent(x), e =>
    e instanceof ConsentPolicyBlocked && e.code === 'browser_answer_shape');
});

test('R-02: even transparent proxies on trusted contexts are rejected', async () => {
  for (const field of ['answer', 'challenge', 'verified', 'observed']) {
    const x = await fixture();
    x[field] = new Proxy(x[field], {});
    await assert.rejects(() => evaluateBrowserConsent(x), e => e instanceof ConsentPolicyBlocked);
  }
});


test('R-02: rejected plain-object getter must not execute during Proxy guard', async () => {
  const x = await fixture();
  let calls = 0;
  Object.defineProperty(x.answer, 'nonce', {
    configurable: true, enumerable: true,
    get() { calls++; return NONCE; },
  });
  await assert.rejects(() => evaluateBrowserConsent(x), e =>
    e instanceof ConsentPolicyBlocked && e.code === 'browser_answer_shape');
  assert.equal(calls, 0);
});
