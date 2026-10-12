// TEST-only generic authorization broker. Policy is rendered from exact trusted
// fixture/schema/commit pins, not request payload or a moving branch head.
import { createRemoteJWKSet,jwtVerify } from 'npm:jose@6.1.0';
import { allowedClaims,approvalBody } from './owner_claims.mjs';
const policy={schema:'__FIXTURE_SCHEMA__',sha:'__WORKFLOW_SHA__',ref:'refs/heads/test/writer-delta-and-production-acceptance-20261011'};
const project='yjmcesdayfmfissghzgm';
const audience='health-writer-test-authorization-'+project;
const jwks=createRemoteJWKSet(new URL('https://token.actions.githubusercontent.com/.well-known/jwks'));
const reply=(body:unknown,status=200)=>new Response(JSON.stringify(body),{status,headers:{'content-type':'application/json','cache-control':'no-store','x-content-type-options':'nosniff'}});
Deno.serve(async(request:Request)=>{
 if(request.method!=='POST')return reply({accepted:false},405);
 const header=request.headers.get('authorization')??'';
 if(!/^Bearer [A-Za-z0-9_.-]+$/.test(header))return reply({accepted:false},401);
 let claims:Record<string,unknown>;
 try{const verified=await jwtVerify(header.slice(7),jwks,{issuer:'https://token.actions.githubusercontent.com',audience,algorithms:['RS256'],clockTolerance:5,maxTokenAge:'10m'});claims=verified.payload;}
 catch{return reply({accepted:false},401);}
 if(!allowedClaims(claims,policy))return reply({accepted:false},403);
 let body:Record<string,unknown>;
 try{const raw=await request.text();if(raw.length>2048)return reply({accepted:false},400);body=JSON.parse(raw);}
 catch{return reply({accepted:false},400);}
 if(!approvalBody(body,policy))return reply({accepted:false},403);
 const url=Deno.env.get('SUPABASE_URL'),key=Deno.env.get('SUPABASE_SERVICE_ROLE_KEY');
 if(url!=='https://'+project+'.supabase.co'||!key)return reply({accepted:false},503);
 try{
  const response=await fetch(url+'/rest/v1/rpc/health_test_authorize_writer_v3',{method:'POST',headers:{apikey:key,authorization:'Bearer '+key,'content-type':'application/json'},
   body:JSON.stringify({p_schema:policy.schema,p_key:body.request_key,p_kind:body.kind,p_digest:body.digest,p_actor:String(claims.actor_id),
    p_repo:String(claims.repository_id),p_workflow_sha:String(claims.workflow_sha),p_jti:String(claims.jti),p_run:String(claims.run_id),p_attempt:String(claims.run_attempt)})});
  if(!response.ok)return reply({accepted:false},409);
  const result=await response.json();
  if(result?.accepted!==true||result?.digest!==body.digest)return reply({accepted:false},500);
  return reply({accepted:true,digest:body.digest,kind:body.kind});
 }catch{return reply({accepted:false},502);}
});
