// Call only AFTER GitHub JWT signature, issuer, audience and age verification.
export function allowedCanonicalClaims(c,p) {
  return c.repository==='Alexio00/HEALTH' && String(c.repository_id)==='1408460030' &&
    c.actor==='Alexio00' && String(c.actor_id)==='308028794' &&
    c.event_name==='workflow_dispatch' && c.ref===p.ref &&
    [`repo:Alexio00/HEALTH:ref:${p.ref}`,`repo:Alexio00@308028794/HEALTH@1408460030:ref:${p.ref}`].includes(c.sub) &&
    c.workflow_ref===`Alexio00/HEALTH/.github/workflows/${p.workflow}@${p.ref}` &&
    c.workflow_sha===p.sha && c.sha===p.sha && /^[a-f0-9]{40}$/.test(p.sha) &&
    ['writer-authorization.yml','code-validation.yml'].includes(p.workflow) &&
    /^\d{1,20}$/.test(String(c.run_id??'')) && /^\d{1,6}$/.test(String(c.run_attempt??'')) &&
    typeof c.jti==='string' && c.jti.length>=8 && c.jti.length<=256;
}
export function canonicalApprovalBody(b) {
  return b!==null && typeof b==='object' && !Array.isArray(b) &&
    Object.keys(b).sort().join(',')==='digest,kind,request_key' &&
    typeof b.request_key==='string' && /^writer-[a-f0-9]{32}$/.test(b.request_key) &&
    ['intent','candidate'].includes(b.kind) && typeof b.digest==='string' && /^[a-f0-9]{64}$/.test(b.digest);
}
