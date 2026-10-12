"""Restricted TCP + real signed OIDC against an isolated synthetic TEST pair."""
import argparse,hashlib,json,os,re,sys,uuid
from pathlib import Path
import psycopg2
from session_pooler_tls import fields,install_ca
from signed_canonical_authorization import authorize
PROJECT='yjmcesdayfmfissghzgm'
class Stop(RuntimeError):pass
def run(control,clinical,phase,pin):
 if not all(re.fullmatch('health_writer_fixture_[a-f0-9]{12}',s) for s in (control,clinical)) or control==clinical:raise Stop('exact_disposable_test_schemas_required')
 if os.environ.get('GITHUB_SHA')!=pin or os.environ.get('GITHUB_ACTOR_ID')!='308028794' or os.environ.get('GITHUB_REF')!='refs/heads/test/writer-delta-and-production-acceptance-20261011':raise Stop('exact_owner_test_dispatch_required')
 ca=Path(os.environ['RUNNER_TEMP'])/'canonical-writer-ca.pem';install_ca(ca)
 cfg,pw=fields(os.environ['HEALTH_TEST_WRITER_DB_URL'],PROJECT,'health_test_ci',ca.resolve())
 c=psycopg2.connect(host=cfg['PGHOST'],port=5432,user=cfg['PGUSER'],password=pw,dbname='postgres',sslmode='verify-full',sslrootcert=str(ca),gssencmode='disable',connect_timeout=15);c.autocommit=True
 checks=[]
 def check(name,value):
  checks.append({'name':name,'passed':bool(value)})
  if not value:raise Stop('failed:'+name)
 def query(sql,args=(),denied=None):
  try:
   with c.cursor() as q:
    q.execute(sql,args)
    if denied:return False
    return q.fetchone()[0] if q.description else None
  except psycopg2.Error as e:
   if denied:return e.pgcode==denied
   raise Stop('canonical_test_sqlstate_'+(e.pgcode or 'UNAVAILABLE')) from None
 def api(fn,*args):return query('SELECT '+control+'.'+fn+'('+','.join(['%s']*len(args))+');',args)
 def approve(key,kind,digest):return authorize(PROJECT,{'request_key':key,'kind':kind,'digest':digest},pin)
 try:
  check('actual_restricted_session_identity',query("SELECT session_user='health_test_ci' AND NOT rolsuper AND NOT rolbypassrls AND NOT rolcreaterole AND NOT rolcreatedb FROM pg_roles WHERE rolname=session_user"))
  check('clinical_tables_not_directly_writable',query('UPDATE '+clinical+'.records SET title=title;',denied='42501'))
  check('policy_not_directly_writable',query('UPDATE '+control+'.runtime_policy SET enabled=true;',denied='42501'))
  check('private_projection_helper_denied',query('SELECT '+control+'.apply_delta_internal(\'[]\',NULL);',denied='42501'))
  check('self_authorization_denied',query('SELECT '+control+'.accept_authorization(NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL);',denied='42501'))
  check('self_semantic_attestation_denied',query('SELECT '+control+'.attest_semantics(NULL,NULL,NULL,\'[]\',\'[]\');',denied='42501'))
  if phase=='prepare':
   key='writer-'+uuid.uuid4().hex
   intent={'action':'UPDATE','user_message_sha256':hashlib.sha256(b'SYNTHETIC CANONICAL SUPABASE TEST').hexdigest(),'conversation_ref':'SYNTHETIC/canonical-network/'+key}
   i=api('submit_intent',key,json.dumps(intent));check('intent_is_unapproved',i['approved'] is False)
   check('unapproved_prepare_denied',query('SELECT '+control+'.prepare(%s);',(key,),denied='P0001'))
   receipt=approve(key,'intent',i['intent_sha']);check('actual_signed_owner_intent',receipt['accepted'])
   prepared=api('prepare',key);check('canonical_operation_prepared',prepared['state']=='PREPARED')
   model=api('request_context',key);row=next(r for r in model['context']['records'] if r['nnn']==1)
   check('approved_context_bound_to_intent',model['intent_sha']==i['intent_sha'])
   # PostgreSQL jsonb canonical text produces the expected_sha. Context contains
   # synthetic rows only; this query never reads a production table.
   expected=model['row_hashes']['records'][model['context']['records'].index(row)]
   changes=[{'table':'records','action':'UPDATE','key':{'record_id':row['record_id']},'expected_sha':expected,'row':{'title':'Synthetic canonical network publication'}}]
   candidate=api('propose',key,json.dumps(changes),None)
   check('candidate_projection_returns_exact_hashes',all(re.fullmatch('[a-f0-9]{64}',candidate[k]) for k in ['candidate_sha','before_sha','after_sha']))
   approve(key,'candidate',candidate['candidate_sha']);check('actual_signed_owner_candidate',True)
   check('missing_independent_semantics_blocks_publish',query('SELECT '+control+'.finalize(%s);',(key,),denied='P0001'))
   result={'status':'ACTUAL_SUPABASE_CANONICAL_PREPARE_PASS','request_key':key,'operation_id':prepared['operation_id'],**candidate}
  else:
   # Administrator supplies only opaque hashes/UUID in a fixture metadata row.
   # No extra general SQL or medical payload is accepted by the workflow.
   meta=api('test_network_target');key=meta['request_key'];candidate={k:meta[k] for k in ['candidate_sha','before_sha','after_sha']}
   approve(key,'candidate',candidate['candidate_sha']);check('exact_signed_candidate_replay',True)
   result=api('finalize',key);check('actual_canonical_publication_finalized',result['state']=='FINALIZED')
   check('canonical_replay_is_idempotent',api('finalize',key)['replayed'])
   check('all_37_registered_results',api('test_network_result',key)['registered_results']==37)
   check('owner_legacy_exception_in_current_audit',api('test_network_result',key)['legacy_exceptions']==1)
   result={'status':'ACTUAL_SUPABASE_CANONICAL_PUBLISH_PASS','request_key':key,'operation_id':meta['operation_id'],**candidate}
  result.update(project_id=PROJECT,control_schema=control,clinical_schema=clinical,workflow_sha=pin,run_id=os.environ.get('GITHUB_RUN_ID'),run_attempt=os.environ.get('GITHUB_RUN_ATTEMPT'),checks=checks,assertions=len(checks),sslmode='verify-full',ca_sha256=__import__('session_pooler_tls').CA_SHA,clinical_semantic_inputs='ADMINISTRATOR_SIMULATED_SYNTHETIC_ONLY',production_deployment=False,production_clinical_writes=False)
  return result
 finally:c.close();ca.unlink(missing_ok=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--control',required=True);p.add_argument('--clinical',required=True);p.add_argument('--phase',choices=['prepare','publish'],required=True);p.add_argument('--pin',required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 try:r=run(a.control,a.clinical,a.phase,a.pin)
 except Exception as e:r={'status':'STOPPED','safe_reason':str(e) if isinstance(e,Stop) else type(e).__name__,'production_clinical_writes':False}
 a.out.write_text(json.dumps(r,indent=2));print(json.dumps(r));raise SystemExit(2 if r['status']=='STOPPED' else 0)
