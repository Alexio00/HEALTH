import assert from 'node:assert/strict';
import { allowedClaims, approvalBody } from './owner_claims.mjs';
const policy={sha:'a'.repeat(40),ref:'refs/heads/test/writer-delta-and-production-acceptance-20261011',schema:'health_writer_fixture_12345678'};
const claims={repository:'Alexio00/HEALTH',repository_id:'1408460030',actor_id:'308028794',actor:'Alexio00',event_name:'workflow_dispatch',ref:policy.ref,
 workflow_ref:`Alexio00/HEALTH/.github/workflows/code-validation.yml@${policy.ref}`,workflow_sha:policy.sha,sha:policy.sha,run_id:'123456789',run_attempt:'1',jti:'synthetic-jti'};
assert(allowedClaims(claims,policy));let checks=1;
for(const [field,value] of Object.entries({repository:'foreign/HEALTH',repository_id:'0',actor_id:'15010426',actor:'Alexio000',event_name:'pull_request',
 ref:'refs/heads/main',workflow_ref:'foreign/workflow',workflow_sha:'b'.repeat(40),sha:'b'.repeat(40),run_id:'-1',run_attempt:'0x1',jti:'short'})){
 assert(!allowedClaims({...claims,[field]:value},policy));checks++;
}
const body={schema:policy.schema,request_key:'synthetic_network',kind:'candidate',digest:'a'.repeat(64)};
assert(approvalBody(body,policy));checks++;
assert(approvalBody({...body,request_key:'SYNTHETIC-DURABLE-123456789abc'},policy));checks++;
for(const invalid of [{...body,schema:'public'},{...body,kind:'arbitrary'},{...body,digest:'x'}, {...body,request_key:"x');drop"},{...body,sql:'arbitrary'},null,[]]){
 assert(!approvalBody(invalid,policy));checks++;
}
console.log(JSON.stringify({status:'OWNER_CLAIM_POLICY_PASS',assertions:checks,cryptographic_jwt_signature:'NOT_TESTED_BY_THIS_UNIT'}));
