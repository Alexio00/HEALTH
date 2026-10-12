// Shared policy checks AFTER cryptographic GitHub OIDC verification.
export function allowedClaims(claims, policy) {
  return claims.repository === 'Alexio00/HEALTH' &&
    String(claims.repository_id) === '1408460030' &&
    String(claims.actor_id) === '308028794' && claims.actor === 'Alexio00' &&
    claims.event_name === 'workflow_dispatch' && claims.ref === policy.ref &&
    claims.workflow_ref === `Alexio00/HEALTH/.github/workflows/code-validation.yml@${policy.ref}` &&
    claims.workflow_sha === policy.sha && claims.sha === policy.sha &&
    /^[a-f0-9]{40}$/.test(policy.sha) &&
    /^\d{1,20}$/.test(String(claims.run_id ?? '')) &&
    /^\d{1,6}$/.test(String(claims.run_attempt ?? '')) &&
    typeof claims.jti === 'string' && claims.jti.length >= 8 && claims.jti.length <= 256;
}
export function approvalBody(body, policy) {
  return body !== null && typeof body === 'object' && !Array.isArray(body) &&
    Object.keys(body).sort().join(',') === 'digest,kind,request_key,schema' &&
    body.schema === policy.schema &&
    typeof body.request_key === 'string' && /^[A-Za-z0-9_-]{1,80}$/.test(body.request_key) &&
    ['intent', 'candidate'].includes(body.kind) && /^[a-f0-9]{64}$/.test(body.digest);
}
