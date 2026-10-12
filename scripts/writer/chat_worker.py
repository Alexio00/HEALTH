"""Bounded chat operator; private medical files stay local and out of GitHub.

Profile contains credential-file paths, not SQL or user-selected destinations.
Authorizations transmit only opaque request UUIDs, kind and SHA-256. Semantic
receipts must be supplied from actual review; this client never fabricates them.
"""
import argparse,configparser,json,os,re,subprocess,time,uuid
from pathlib import Path
import psycopg2
from session_pooler_tls import fields
from postgres_upload_journal import PostgresUploadJournal
from source_drive_provider import SourceUploader,OWNER,VERIFIER
from drive_provider import DriveTransport
from drive_resumable import Wire,file_digest

PROJECT='ffvqgbslvjocbwfurxrv'
class WorkerStop(RuntimeError):pass
def read_json(path,limit=64*1024**2):
 p=Path(path)
 if p.is_symlink() or not p.is_file() or p.stat().st_size>limit:raise WorkerStop('private_input_file_rejected')
 try:return json.loads(p.read_text(encoding='utf-8-sig'))
 except (ValueError,UnicodeError):raise WorkerStop('private_input_json_rejected') from None
def save_private(root,name,value):
 root=Path(root);target=root/name
 if root.is_symlink() or not root.is_dir() or target.is_symlink() or not target.resolve().is_relative_to(root.resolve()):raise WorkerStop('private_output_boundary_rejected')
 # Each step leaves immutable local evidence. Never overwrite prior results.
 target=root/(name+'.'+uuid.uuid4().hex[:12]+'.json')
 with target.open('x',encoding='utf-8') as f:json.dump(value,f,ensure_ascii=False,indent=2)
 target.chmod(0o600);return target
def gh(*args):
 p=subprocess.run(['gh',*args],capture_output=True,text=True,encoding='utf-8',timeout=60)
 if p.returncode:raise WorkerStop('github_operation_failed')
 return p.stdout
def approve(profile,key,metadata):
 if metadata.get('request_key')!=key:raise WorkerStop('authorization_request_mismatch')
 gh('auth','switch','--user','Alexio00')
 if json.loads(gh('api','user'))['id']!=308028794:raise WorkerStop('github_owner_identity_rejected')
 pin=json.loads(gh('api','repos/Alexio00/HEALTH/actions/variables/HEALTH_WRITER_ACCEPTED_SHA'))['value']
 if pin!=profile['accepted_sha']:raise WorkerStop('accepted_runtime_commit_changed')
 title='Writer authorization '+metadata['kind']+' '+key
 previous=json.loads(gh('run','list','--repo','Alexio00/HEALTH','--workflow','writer-authorization.yml','--limit','30','--json','databaseId,displayTitle'))
 seen={x['databaseId'] for x in previous}
 gh('workflow','run','writer-authorization.yml','--repo','Alexio00/HEALTH','--ref','main','-f','request_key='+key,'-f','kind='+metadata['kind'],'-f','digest='+metadata['digest'])
 deadline=time.monotonic()+300
 while time.monotonic()<deadline:
  runs=json.loads(gh('run','list','--repo','Alexio00/HEALTH','--workflow','writer-authorization.yml','--branch','main','--limit','30','--json','databaseId,displayTitle,headSha,status,conclusion,event'))
  matches=[x for x in runs if x['databaseId'] not in seen and x['displayTitle']==title and x['headSha']==pin and x['event']=='workflow_dispatch']
  if len(matches)>1:raise WorkerStop('ambiguous_authorization_runs')
  if matches and matches[0]['status']=='completed':
   if matches[0]['conclusion']!='success':raise WorkerStop('signed_authorization_failed')
   return {'run_id':matches[0]['databaseId'],'head_sha':pin,'kind':metadata['kind'],'digest':metadata['digest']}
  time.sleep(5)
 raise WorkerStop('authorization_still_pending_check_existing_run')
def google(profile,verifier=False):
 file=Path(profile['reader_oauth_file'] if verifier else profile['writer_oauth_file'])
 remote=profile['reader_remote'] if verifier else profile['writer_remote']
 # Refresh through the existing URL-consent credential; never print its data.
 p=subprocess.run(['rclone','lsf',remote+':','--max-depth','1','--dirs-only','--config',str(file),'--log-level','ERROR'],capture_output=True,timeout=90)
 if p.returncode:raise WorkerStop('google_token_refresh_failed')
 def token():
  c=configparser.ConfigParser(interpolation=None);c.read(file,encoding='utf-8');return json.loads(c[remote]['token'])['access_token']
 t=DriveTransport(token)
 if t.request('/drive/v3/about?fields=user(emailAddress)')['user']['emailAddress']!=(VERIFIER if verifier else OWNER):raise WorkerStop('google_account_identity_rejected')
 return t
def run(a):
 profile=read_json(a.profile,16384)
 if profile.get('project_id')!=PROJECT or profile.get('schema')!='health_writer' or not re.fullmatch('[a-f0-9]{40}',profile.get('accepted_sha','')):raise WorkerStop('exact_production_profile_required')
 verifier=a.action in ('review','attest','verify-sources')
 role='health_writer_verifier_login' if verifier else 'health_writer'
 cfg,pw=fields(Path(profile['verifier_connection_file'] if verifier else profile['writer_connection_file']).read_text().strip(),PROJECT,role,Path(profile['ca_file']).resolve())
 c=psycopg2.connect(host=cfg['PGHOST'],port=5432,user=cfg['PGUSER'],password=pw,dbname='postgres',sslmode='verify-full',sslrootcert=cfg['PGSSLROOTCERT'],gssencmode='disable',connect_timeout=15);c.autocommit=True
 def query(sql,args=()):
  try:
   with c.cursor() as q:q.execute(sql,args);return q.fetchone()[0] if q.description else None
  except psycopg2.Error as e:raise WorkerStop('writer_sqlstate_'+(e.pgcode or 'UNAVAILABLE')) from None
 def api(fn,*args):return query('SELECT health_writer.'+fn+'('+','.join(['%s']*len(args))+');',args)
 key=a.request_key or 'writer-'+uuid.uuid4().hex
 if not re.fullmatch('writer-[a-f0-9]{32}',key):raise WorkerStop('opaque_request_key_required')
 try:
  if not query("SELECT session_user=%s AND NOT rolsuper AND NOT rolbypassrls AND NOT rolcreaterole AND NOT rolcreatedb FROM pg_roles WHERE rolname=session_user",(role,)):raise WorkerStop('restricted_role_identity_rejected')
  if a.action=='start':
   if not a.input:raise WorkerStop('owner_intent_file_required')
   result=api('submit_intent',key,json.dumps(read_json(a.input,8192)))
   receipt=approve(profile,key,api('authorization_request',key,'intent'))
   result={'intent':result,'authorization':receipt,'preparation':api('prepare',key),'model':api('request_context',key)}
  elif a.action=='context':result=api('request_context',key)
  elif a.action=='propose':
   if not a.input:raise WorkerStop('changes_file_required')
   changes=read_json(a.input);manifest=read_json(a.manifest) if a.manifest else None
   result=api('propose',key,json.dumps(changes),json.dumps(manifest) if manifest is not None else None)
   result['authorization']=approve(profile,key,api('authorization_request',key,'candidate'))
  elif a.action=='upload':
   if not a.input or not a.file:raise WorkerStop('source_plan_and_binary_file_required')
   source=read_json(a.input,16384);sha,size=file_digest(a.file)
   if (sha,size)!=(source.get('sha256'),source.get('size_bytes')):raise WorkerStop('source_local_digest_binding_mismatch')
   planned=api('plan_source',key,json.dumps(source),'google-drive','HEALTH_PRIMARY');marker=planned['marker']
   api('source_uncertain',key,source['source_id'])
   journal=PostgresUploadJournal(c);folder=profile['primary_folder']
   with journal.lock(marker):journal.plan(marker,folder,source['source_id'],sha,size)
   uploader=SourceUploader(folder,google(profile),journal)
   object_id=uploader.upload_file(marker,source['source_id'],a.file)
   result={'source_id':source['source_id'],'marker':marker,'object_id':object_id,'source_row':source,'provider':'google-drive','account_alias':'HEALTH_PRIMARY','transport_complete':True,'independent_verification':'PENDING'}
  elif a.action=='review':result=api('review_candidate',key)
  elif a.action=='verify-sources':
   review=api('review_candidate',key);reader=google(profile,True);wire=Wire(reader.token);verified=[]
   for m in review['payload'].get('source_manifest',[]):
    row=m['source_row'];obj=m['object_id'];api('begin_source_check',key,row['source_id'])
    def meta():return reader.request('/drive/v3/files/'+obj+'?fields=id,parents,properties,size,version,trashed,owners(emailAddress),capabilities(canEdit)')
    before=meta()
    if before.get('parents')!=[profile['primary_folder']] or before.get('owners')!=[{'emailAddress':OWNER}] or before.get('trashed') is not False or before.get('capabilities',{}).get('canEdit') is not False or before.get('properties',{}).get('health_marker')!=m['marker'] or before.get('properties',{}).get('health_source_id')!=row['source_id'] or before.get('properties',{}).get('health_writer_protocol')!='v1':raise WorkerStop('independent_source_metadata_binding_rejected')
    sha,size=wire.download_digest(obj,row['size_bytes'])
    if sha!=row['sha256'] or before!=meta():raise WorkerStop('independent_source_byte_or_version_mismatch')
    verified.append(api('attest_source',key,row['source_id'],m['marker'],obj,sha,size))
   result={'candidate_sha':review['candidate_sha'],'after_sha':review['after_sha'],'sources_verified':len(verified),'receipts':verified}
  elif a.action=='attest':
   if not a.input:raise WorkerStop('actual_review_receipts_file_required')
   evidence=read_json(a.input);review=api('review_candidate',key)
   if evidence.get('candidate_sha')!=review['candidate_sha'] or evidence.get('after_sha')!=review['after_sha']:raise WorkerStop('review_evidence_candidate_mismatch')
   result=api('attest_semantics',key,review['candidate_sha'],review['after_sha'],json.dumps(evidence['receipts']),json.dumps(evidence.get('labs',[])))
  elif a.action=='publish':result=api('finalize',key)
  elif a.action=='abandon':result=api('abandon',key)
  elif a.action=='status':result=api('request_status',key)
  else:raise WorkerStop('unsupported_bounded_action')
  save_private(profile['private_evidence_folder'],key+'.'+a.action,result)
  return {'status':'WRITER_BOUNDED_STEP_COMPLETED','action':a.action,'request_key':key,'state':result.get('state') if isinstance(result,dict) else None}
 finally:c.close()
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--profile',type=Path,required=True);p.add_argument('action',choices=['start','context','propose','upload','review','verify-sources','attest','publish','abandon','status']);p.add_argument('--request-key');p.add_argument('--input',type=Path);p.add_argument('--manifest',type=Path);p.add_argument('--file',type=Path);a=p.parse_args()
 try:r=run(a)
 except Exception as e:r={'status':'STOPPED','safe_reason':str(e) if isinstance(e,WorkerStop) else type(e).__name__};print(json.dumps(r));raise SystemExit(2)
 print(json.dumps(r))
