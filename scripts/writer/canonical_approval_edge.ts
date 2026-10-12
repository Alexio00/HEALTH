// Policy rendered from the accepted commit; body never chooses project/schema.
import {createRemoteJWKSet,jwtVerify} from 'npm:jose@6.1.0';
import {allowedCanonicalClaims,canonicalApprovalBody} from './canonical_owner_claims.mjs';
const policy=__CANONICAL_POLICY__;
const jwks=createRemoteJWKSet(new URL('https://token.actions.githubusercontent.com/.well-known/jwks'));
const reply=(accepted:boolean,status=200,extra:Record<string,unknown>={})=>new Response(JSON.stringify({accepted,...extra}),{status,headers:{'content-type':'application/json','cache-control':'no-store','x-content-type-options':'nosniff'}});
Deno.serve(async(req:Request)=>{
 if(req.method!=='POST')return reply(false,405);
 const header=req.headers.get('authorization')??'';
 if(!/^Bearer [A-Za-z0-9_.-]+$/.test(header))return reply(false,401);
 let claims:Record<string,unknown>;
 try{claims=(await jwtVerify(header.slice(7),jwks,{issuer:'https://token.actions.githubusercontent.com',audience:policy.audience,algorithms:['RS256'],clockTolerance:5,maxTokenAge:'10m'})).payload;}
 catch{return reply(false,401);}
 if(!allowedCanonicalClaims(claims,policy))return reply(false,403);
 let body:Record<string,unknown>;
 try{const text=await req.text();if(text.length>2048)return reply(false,400);body=JSON.parse(text);}
 catch{return reply(false,400);}
 if(!canonicalApprovalBody(body))return reply(false,403);
 const url=Deno.env.get('SUPABASE_URL'),key=Deno.env.get('SUPABASE_SERVICE_ROLE_KEY');
 if(url!=='https://'+policy.project+'.supabase.co'||!key)return reply(false,503);
 try{
  const r=await fetch(url+'/rest/v1/rpc/'+policy.rpc,{method:'POST',headers:{apikey:key,authorization:'Bearer '+key,'content-type':'application/json'},body:JSON.stringify({
   p_key:body.request_key,p_kind:body.kind,p_digest:body.digest,p_actor:String(claims.actor_id),p_repo:String(claims.repository_id),
   p_workflow_sha:String(claims.workflow_sha),p_jti:String(claims.jti),p_run:String(claims.run_id),p_attempt:String(claims.run_attempt)})});
  if(!r.ok)return reply(false,409);
  const result=await r.json();if(result?.accepted!==true||result?.digest!==body.digest)return reply(false,500);
  return reply(true,200,{digest:body.digest,kind:body.kind});
 }catch{return reply(false,502);}
});
