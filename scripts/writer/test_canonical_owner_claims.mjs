import assert from 'node:assert/strict';
import {allowedCanonicalClaims,canonicalApprovalBody} from './canonical_owner_claims.mjs';
const p={sha:'a'.repeat(40),ref:'refs/heads/main',workflow:'writer-authorization.yml'};
const c={repository:'Alexio00/HEALTH',repository_id:'1408460030',actor:'Alexio00',actor_id:'308028794',event_name:'workflow_dispatch',ref:p.ref,
 sub:`repo:Alexio00/HEALTH:ref:${p.ref}`,workflow_ref:`Alexio00/HEALTH/.github/workflows/${p.workflow}@${p.ref}`,workflow_sha:p.sha,sha:p.sha,run_id:'123',run_attempt:'1',jti:'signed-token-123'};
const b={request_key:'writer-'+'a'.repeat(32),kind:'intent',digest:'b'.repeat(64)};
assert(allowedCanonicalClaims(c,p));assert(canonicalApprovalBody(b));
assert(allowedCanonicalClaims({...c,sub:`repo:Alexio00@308028794/HEALTH@1408460030:ref:${p.ref}`},p));
assert(!allowedCanonicalClaims({...c,sub:`repo:Alexio00@1/HEALTH@1408460030:ref:${p.ref}`},p));
let negative=1;
for(const [key,value] of Object.entries({repository:'fork/HEALTH',repository_id:'1',actor:'other',actor_id:'1',event_name:'pull_request',ref:'refs/heads/other',sub:'repo:fork/HEALTH:ref:refs/heads/main',workflow_ref:'other',workflow_sha:'b'.repeat(40),sha:'b'.repeat(40),run_id:'bad',run_attempt:'bad',jti:'short'})){
 assert(!allowedCanonicalClaims({...c,[key]:value},p));negative++;
}
for(const value of [null,[],{}, {...b,schema:'public'}, {...b,request_key:'REC-20261012-001'}, {...b,kind:'publish'}, {...b,digest:'short'}]){assert(!canonicalApprovalBody(value));negative++;}
assert(canonicalApprovalBody({...b,kind:'candidate'}));
console.log(JSON.stringify({status:'CANONICAL_OWNER_POLICY_BOUNDARIES_PASS',positive:4,negative,cryptographic_signature_verification:'NOT_SIMULATED_HERE'}));
