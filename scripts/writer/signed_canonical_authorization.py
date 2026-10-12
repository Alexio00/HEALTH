"""Exact owner-dispatched OIDC authorization; no medical payload or SQL login."""
import json,os,re,urllib.error,urllib.parse,urllib.request
from pathlib import Path

POLICIES={
 'yjmcesdayfmfissghzgm':('health-writer-canonical-test-yjmcesdayfmfissghzgm','health-test-canonical-writer-v1','refs/heads/test/writer-delta-and-production-acceptance-20261011'),
 'ffvqgbslvjocbwfurxrv':('health-writer-authorization-v1-ffvqgbslvjocbwfurxrv','health-writer-authorization-v1','refs/heads/main')}
class AuthorizationStop(RuntimeError):pass
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):return None
def authorize(project,metadata,expected_sha):
 if project not in POLICIES:raise AuthorizationStop('authorization_project_rejected')
 audience,function,ref=POLICIES[project]
 if os.environ.get('GITHUB_REPOSITORY')!='Alexio00/HEALTH' or os.environ.get('GITHUB_ACTOR_ID')!='308028794' or os.environ.get('GITHUB_REF')!=ref or os.environ.get('GITHUB_SHA')!=expected_sha or not re.fullmatch('[a-f0-9]{40}',expected_sha):raise AuthorizationStop('exact_owner_dispatch_required')
 if set(metadata)!={'request_key','kind','digest'} or not re.fullmatch('writer-[a-f0-9]{32}',metadata.get('request_key','')) or metadata.get('kind') not in ('intent','candidate') or not re.fullmatch('[a-f0-9]{64}',metadata.get('digest','')):raise AuthorizationStop('opaque_exact_authorization_body_required')
 target=os.environ.get('ACTIONS_ID_TOKEN_REQUEST_URL','');token=os.environ.get('ACTIONS_ID_TOKEN_REQUEST_TOKEN','');u=urllib.parse.urlsplit(target)
 if u.scheme!='https' or not (u.hostname or '').endswith('.actions.githubusercontent.com') or u.username or u.password or not token:raise AuthorizationStop('trusted_oidc_endpoint_required')
 opener=urllib.request.build_opener(NoRedirect)
 def request(req):
  try:
   with opener.open(req,timeout=30) as response:
    data=response.read(16385)
    if len(data)>16384:raise AuthorizationStop('authorization_response_limit')
    return json.loads(data)
  except urllib.error.HTTPError as e:raise AuthorizationStop('authorization_http_'+str(e.code)) from None
  except (urllib.error.URLError,ValueError,TimeoutError):raise AuthorizationStop('authorization_transport_failed') from None
 value=request(urllib.request.Request(target+('&' if u.query else '?')+urllib.parse.urlencode({'audience':audience}),headers={'Authorization':'Bearer '+token}))
 jwt=value.get('value','')
 if not re.fullmatch('[A-Za-z0-9_.-]+',jwt):raise AuthorizationStop('signed_token_missing')
 result=request(urllib.request.Request('https://'+project+'.supabase.co/functions/v1/'+function,data=json.dumps(metadata).encode(),headers={'Authorization':'Bearer '+jwt,'Content-Type':'application/json'},method='POST'))
 if result.get('accepted') is not True or result.get('digest')!=metadata['digest'] or result.get('kind')!=metadata['kind']:raise AuthorizationStop('exact_authorization_receipt_required')
 return {'accepted':True,'kind':metadata['kind'],'digest':metadata['digest'],'workflow_sha':expected_sha,'run_id':os.environ.get('GITHUB_RUN_ID'),'run_attempt':os.environ.get('GITHUB_RUN_ATTEMPT'),'signature':'ACTUAL_GITHUB_JWKS_RS256'}
if __name__=='__main__':
 try:
  value=authorize('ffvqgbslvjocbwfurxrv',{k:os.environ[v] for k,v in [('request_key','WRITER_REQUEST_KEY'),('kind','WRITER_APPROVAL_KIND'),('digest','WRITER_APPROVAL_DIGEST')]},os.environ['HEALTH_WRITER_ACCEPTED_SHA'])
  Path(os.environ['WRITER_APPROVAL_OUT']).write_text(json.dumps(value,indent=2));print(json.dumps(value))
 except Exception as e:print(json.dumps({'accepted':False,'safe_reason':str(e) if isinstance(e,AuthorizationStop) else type(e).__name__}));raise SystemExit(2)
