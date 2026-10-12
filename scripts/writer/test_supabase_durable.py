#!/usr/bin/env python3
"""Owner-dispatched restricted TCP probe against one administrator-created TEST fixture.

No DDL, approval changes, arbitrary SQL or production project. Credentials are
passed only through a whitelisted child environment, not argv or output.
"""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import parse_qs, unquote, urlparse

TEST_PROJECT='yjmcesdayfmfissghzgm'

def connection_fields(raw):
    try:
        url=urlparse(raw)
        host=url.hostname or ''
        user=unquote(url.username or '')
        port=url.port or 5432
    except (TypeError,ValueError):
        raise RuntimeError('invalid_test_database_locator') from None
    direct=host=='db.'+TEST_PROJECT+'.supabase.co' and user in ('health_test_ci','health_test_ci.'+TEST_PROJECT)
    pooler=bool(re.fullmatch(r'(?:[a-z0-9-]+\.){1,2}pooler\.supabase\.com',host)) and user=='health_test_ci.'+TEST_PROJECT
    if url.scheme not in ('postgres','postgresql') or not (direct or pooler) or url.path not in ('/postgres','') or not url.password:
        raise RuntimeError('exact_test_project_restricted_role_required')
    query=parse_qs(url.query,keep_blank_values=True)
    if any(k not in ('sslmode','sslrootcert','connect_timeout','application_name') or len(v)!=1 for k,v in query.items()):
        raise RuntimeError('unreviewed_connection_option')
    mode=query.get('sslmode',['require'])[0]
    if mode not in ('require','verify-ca','verify-full'):
        raise RuntimeError('encrypted_test_connection_required')
    fields={'PGHOST':host,'PGPORT':str(port),'PGUSER':user,'PGPASSWORD':unquote(url.password),
            'PGDATABASE':'postgres','PGSSLMODE':mode,'PGCONNECT_TIMEOUT':'10','PGAPPNAME':'health-durable-test-probe'}
    if 'sslrootcert' in query: fields['PGSSLROOTCERT']=query['sslrootcert'][0]
    return fields

def suite(schema,phase,expected_sha):
    if not re.fullmatch(r'health_writer_fixture_[a-f0-9]{12}',schema): raise RuntimeError('exact_private_fixture_schema_required')
    if not re.fullmatch(r'[a-f0-9]{40}',expected_sha) or os.environ.get('GITHUB_SHA')!=expected_sha:
        raise RuntimeError('workflow_commit_pin_mismatch')
    if os.environ.get('GITHUB_ACTOR_ID')!='308028794' or os.environ.get('GITHUB_REPOSITORY')!='Alexio00/HEALTH':
        raise RuntimeError('owner_dispatch_required')
    env={k:v for k,v in os.environ.items() if k.upper() in {'PATH','HOME','SYSTEMROOT','WINDIR','TEMP','TMP','COMSPEC','PATHEXT'}}
    fields=connection_fields(os.environ.get('HEALTH_TEST_WRITER_DB_URL',''))
    env.update(fields)
    checks=[]
    def check(name,ok,**details):
        checks.append({'name':name,'passed':bool(ok),**details})
        if not ok: raise RuntimeError('failed:'+name)
    def execute(sql,expected=None,conninfo=False):
        p=subprocess.run(['psql','-X','-q','-A','-t','-v','ON_ERROR_STOP=1'],
                         input='\\set VERBOSITY verbose\n'+('\\conninfo\n' if conninfo else '')+sql,
                         text=True,encoding='utf-8',capture_output=True,env=env,timeout=30)
        match=re.search(r'ERROR:\s+([0-9A-Z]{5}):',p.stderr)
        code=match[1] if match else None
        if expected: return p.returncode!=0 and code==expected
        if p.returncode: raise RuntimeError('restricted_database_call_failed:'+(code or 'NO_SERVER_SQLSTATE'))
        return p.stdout.strip()
    key='SYNTHETIC-DURABLE-'+schema.removeprefix('health_writer_fixture_')
    def api(fn,request=key): return json.loads(execute(f"SELECT {schema}.{fn}('{request}');"))
    raw=execute("SELECT jsonb_build_object('role',current_user,'session_user',session_user,'tcp',inet_client_addr() IS NOT NULL,'super',rolsuper,'bypass',rolbypassrls,'create_role',rolcreaterole,'create_db',rolcreatedb) FROM pg_roles WHERE rolname=current_user;",conninfo=True)
    identity=json.loads(raw.splitlines()[-1])
    tls=bool(re.search(r'SSL connection\s*\(',raw))
    check('actual_test_restricted_tcp_identity',identity['role']=='health_test_ci' and identity['session_user']=='health_test_ci' and identity['tcp'] and not any(identity[k] for k in ('super','bypass','create_role','create_db')))
    check('actual_client_tls',tls,sslmode=fields['PGSSLMODE'],scope='TEST client leg; not production executor or backend TLS proof')
    for name,sql in {
        'clinical_update_denied':f"UPDATE {schema}.records SET title='forbidden';",
        'clinical_delete_denied':f"DELETE FROM {schema}.records;",
        'operation_update_denied':f"UPDATE {schema}.operations SET state='FINALIZED';",
        'intent_self_approval_denied':f"UPDATE {schema}.writer_intents SET approved=true;",
        'validation_forgery_denied':f"DELETE FROM {schema}.writer_validation_results;",
        'allocator_mutation_denied':f"DELETE FROM {schema}.id_reservations;",
        'internal_publish_denied':f"SELECT {schema}.publish_internal('{key}',NULL);",
        'foreign_request_denied':f"SELECT {schema}.prepare('{key}-FOREIGN');"
    }.items(): check(name,execute(sql,'42501'),sqlstate='42501')
    check('expired_intent_denied',execute(f"SELECT {schema}.prepare('{key}-EXPIRED');",'P0001'),sqlstate='P0001')
    if phase=='prepare':
        prepared=api('prepare')
        check('actual_durable_prepare',prepared['state']=='PREPARED' and prepared['nnn']==3)
        check('actual_resume_same_operation',api('prepare')==prepared)
        state=api('request_status')
    else:
        check('durable_prepared_before_publish',api('request_status')['state']=='PREPARED')
        committed=api('finalize')
        check('actual_atomic_finalized',committed['state']=='FINALIZED' and not committed['replayed'])
        state=api('request_status')
        check('status_reconciles_commit',state['state']=='FINALIZED' and state['candidate_sha'] is not None)
        check('actual_finalized_replay',api('finalize')['replayed'])
        check('finalized_abandon_denied',execute(f"SELECT {schema}.abandon('{key}');",'P0001'),sqlstate='P0001')
    return {'status':'SUPABASE_TEST_DURABLE_'+phase.upper()+'_TCP_PASS','project_id':TEST_PROJECT,
            'fixture_schema':schema,'phase':phase,'workflow_sha':expected_sha,
            'run_id':os.environ['GITHUB_RUN_ID'],'run_attempt':os.environ['GITHUB_RUN_ATTEMPT'],
            'checks':checks,'assertions':len(checks),'operation_metadata':state,
            'approval_and_semantic_inputs':'ADMINISTRATOR_SYNTHETIC_SIMULATION',
            'actual_supabase_restricted_role_tcp':True,'production_enablement':False,
            'production_executor_tls':'NOT_PROVEN','source_saga_integration':'NOT_RUN'}

def self_test():
    rejected=[]
    for name,url in {
        'production_project':'postgresql://health_test_ci:x@db.ffvqgbslvjocbwfurxrv.supabase.co/postgres',
        'administrator':'postgresql://postgres:x@db.yjmcesdayfmfissghzgm.supabase.co/postgres',
        'unencrypted':'postgresql://health_test_ci:x@db.yjmcesdayfmfissghzgm.supabase.co/postgres?sslmode=disable',
        'sql_option':'postgresql://health_test_ci:x@db.yjmcesdayfmfissghzgm.supabase.co/postgres?options=-crole%3Dpostgres',
        'other_database':'postgresql://health_test_ci:x@db.yjmcesdayfmfissghzgm.supabase.co/other'
    }.items():
        try: connection_fields(url)
        except RuntimeError: rejected.append(name)
    assert len(rejected)==5
    good=connection_fields('postgresql://health_test_ci:x@db.yjmcesdayfmfissghzgm.supabase.co/postgres?sslmode=require')
    assert good['PGUSER']=='health_test_ci' and good['PGSSLMODE']=='require'
    pooler=connection_fields('postgresql://health_test_ci.yjmcesdayfmfissghzgm:x@aws-0-us-west-1.pooler.supabase.com/postgres?sslmode=require')
    assert pooler['PGUSER']=='health_test_ci.'+TEST_PROJECT
    print(json.dumps({'status':'SELF_TEST_PASS','rejected_unsafe_connection_classes':5,'direct_and_pooler_forms':2}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--schema');p.add_argument('--phase',choices=['prepare','publish'])
    p.add_argument('--expected-sha');p.add_argument('--out',type=Path);p.add_argument('--self-test',action='store_true');a=p.parse_args()
    if a.self_test: self_test();sys.exit(0)
    if not all((a.schema,a.phase,a.expected_sha,a.out)): p.error('schema/phase/expected-sha/out required')
    try: result=suite(a.schema,a.phase,a.expected_sha)
    except Exception as error:
        result={'status':'STOPPED','safe_reason':str(error) if isinstance(error,RuntimeError) else type(error).__name__,'production_enablement':False}
    a.out.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='checks'}))
    if result['status']=='STOPPED': sys.exit(2)
