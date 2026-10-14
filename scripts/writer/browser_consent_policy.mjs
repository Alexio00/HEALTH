/**
 * HEALTH Browser Exact Consent: deterministic policy, NOT an authorization issuer.
 *
 * `verified` must come from a fresh trusted Supabase Auth / session / owner
 * lookup and request Origin/CSRF checks. `observed` must come from the bounded
 * Writer's current private readback. Neither may be supplied by the browser,
 * ChatGPT, or a GitHub workflow input.
 *
 * A MATCH result is NOT a signature, permission to publish, or a durable
 * receipt. Atomic single-use consumption and a separately accepted broker
 * remain mandatory before any mutating Writer RPC.
 */

const HEX64 = /^[a-f0-9]{64}$/;
const HEX40 = /^[a-f0-9]{40}$/;
const KEY = /^writer-[a-f0-9]{32}$/;
const UUID = /^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/;
const MAX_TTL_MS = 5 * 60 * 1000;

export class ConsentPolicyBlocked extends Error {
  constructor(code) {
    super(code);
    this.code = code;
    this.name = 'ConsentPolicyBlocked';
  }
}
const fail = code => { throw new ConsentPolicyBlocked(code); };

function exactPlainObject(value, keys, code) {
  if (value === null || typeof value !== 'object' || Array.isArray(value) ||
      Object.getPrototypeOf(value) !== Object.prototype ||
      Reflect.ownKeys(value).length !== keys.length ||
      keys.some(k => !Object.hasOwn(value, k))) fail(code);
  for (const key of keys) {
    const d = Object.getOwnPropertyDescriptor(value, key);
    if (!d || !Object.hasOwn(d, 'value') || d.value === undefined ||
        typeof d.value === 'function' || typeof d.value === 'symbol' ||
        typeof d.value === 'bigint' ||
        (typeof d.value === 'number' && !Number.isFinite(d.value))) fail(code);
  }
}
function stringLike(value, regex, code) {
  if (typeof value !== 'string' || !regex.test(value)) fail(code);
}
function clockValue(value, code) {
  if (!Number.isSafeInteger(value) || value < 0) fail(code);
}
function constantTimeHexEquals(a, b) {
  if (typeof a !== 'string' || typeof b !== 'string' || a.length !== 64 || b.length !== 64) return false;
  let mismatch = 0;
  for (let i = 0; i < 64; i++) mismatch |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return mismatch === 0;
}

export async function nonceHash(nonceHex) {
  stringLike(nonceHex, HEX64, 'nonce_invalid');
  const bytes = new TextEncoder().encode(nonceHex);
  const sha = await crypto.subtle.digest('SHA-256', bytes);
  return [...new Uint8Array(sha)].map(n => n.toString(16).padStart(2, '0')).join('');
}

const CHALLENGE = [
  'challenge_id','request_key','kind','owner_uid','session_id',
  'candidate_sha','before_sha','after_sha','review_sha','accepted_sha',
  'nonce_sha','issued_at_ms','expires_at_ms','state'
];
const VERIFIED = [
  'owner_uid','session_id','jwt_verified','session_live','owner_allowlisted',
  'origin_verified','csrf_verified'
];
const OBSERVED = [
  'request_key','candidate_sha','before_sha','after_sha','review_sha',
  'accepted_sha','state'
];
const ANSWER = ['challenge_id','nonce','displayed_review_sha','decision'];

/**
 * Evaluate an exact candidate review decision.
 *
 * All arguments except `answer` must be private, independently checked server
 * inputs. `nowMs` is trusted server time. The response has no credential and
 * MUST NOT be reused as a Writer approval receipt.
 */
export async function evaluateBrowserConsent({challenge, verified, observed, answer, nowMs}) {
  exactPlainObject(challenge, CHALLENGE, 'challenge_shape');
  exactPlainObject(verified, VERIFIED, 'trusted_context_shape');
  exactPlainObject(observed, OBSERVED, 'writer_readback_shape');
  exactPlainObject(answer, ANSWER, 'browser_answer_shape');
  clockValue(nowMs, 'trusted_clock_invalid');

  stringLike(challenge.challenge_id, UUID, 'challenge_id_invalid');
  stringLike(challenge.request_key, KEY, 'request_key_invalid');
  if (challenge.kind !== 'candidate') fail('unapproved_consent_kind');
  stringLike(challenge.owner_uid, UUID, 'owner_uid_invalid');
  stringLike(challenge.session_id, UUID, 'session_id_invalid');
  for (const k of ['candidate_sha','before_sha','after_sha','review_sha','nonce_sha'])
    stringLike(challenge[k], HEX64, 'challenge_digest_invalid');
  stringLike(challenge.accepted_sha, HEX40, 'challenge_release_invalid');
  clockValue(challenge.issued_at_ms, 'issued_at_invalid');
  clockValue(challenge.expires_at_ms, 'expires_at_invalid');
  if (challenge.expires_at_ms <= challenge.issued_at_ms ||
      challenge.expires_at_ms - challenge.issued_at_ms > MAX_TTL_MS)
    fail('challenge_ttl_invalid');
  if (nowMs < challenge.issued_at_ms || nowMs >= challenge.expires_at_ms)
    fail('challenge_expired');
  if (challenge.state !== 'PENDING') fail('challenge_not_pending');

  stringLike(verified.owner_uid, UUID, 'verified_owner_invalid');
  stringLike(verified.session_id, UUID, 'verified_session_invalid');
  if (verified.jwt_verified !== true || verified.session_live !== true ||
      verified.owner_allowlisted !== true || verified.origin_verified !== true ||
      verified.csrf_verified !== true) fail('verified_server_evidence_required');
  if (verified.owner_uid !== challenge.owner_uid ||
      verified.session_id !== challenge.session_id)
    fail('owner_session_mismatch');

  stringLike(answer.challenge_id, UUID, 'answer_challenge_invalid');
  stringLike(answer.nonce, HEX64, 'answer_nonce_invalid');
  stringLike(answer.displayed_review_sha, HEX64, 'answer_review_invalid');
  if (answer.decision !== 'confirm' && answer.decision !== 'decline')
    fail('answer_decision_invalid');
  if (answer.challenge_id !== challenge.challenge_id) fail('challenge_mismatch');
  if (!constantTimeHexEquals(await nonceHash(answer.nonce), challenge.nonce_sha))
    fail('nonce_mismatch');
  if (answer.displayed_review_sha !== challenge.review_sha)
    fail('displayed_review_mismatch');

  stringLike(observed.request_key, KEY, 'writer_request_invalid');
  for (const k of ['candidate_sha','before_sha','after_sha','review_sha'])
    stringLike(observed[k], HEX64, 'writer_digest_invalid');
  stringLike(observed.accepted_sha, HEX40, 'writer_release_invalid');
  if (observed.state !== 'PREPARED') fail('writer_operation_not_prepared');
  for (const k of ['request_key','candidate_sha','before_sha','after_sha',
                   'review_sha','accepted_sha']) {
    if (observed[k] !== challenge[k]) fail('stale_or_changed_candidate');
  }

  // This is intentionally NOT {approved: true}, nor a signed owner receipt.
  return Object.freeze({
    outcome: 'POLICY_MATCH_ONLY',
    challenge_id: challenge.challenge_id,
    request_key: challenge.request_key,
    candidate_sha: challenge.candidate_sha,
    decision: answer.decision
  });
}
