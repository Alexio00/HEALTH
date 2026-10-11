#!/usr/bin/env python3
"""Disposable synthetic PG17 TCP-role acceptance; no production credentials/data.

Admin provisions candidates/semantic receipts explicitly as a simulation.
Network writer authenticates using a unique synthetic SCRAM login and receives
only the fixture publication/status entrypoints. Never SET ROLE for DML tests.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import importlib.util
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import uuid

HERE=Path(__file__).resolve().parent

class DatabaseCallError(RuntimeError):
    def __init__(self,role,sqlstate):
        self.sqlstate=sqlstate
        super().__init__('database_call_failed:'+role+':'+(sqlstate or 'NO_SERVER_SQLSTATE'))

def run_suite(container=None,database='postgres'):
    if database!='postgres' and not re.fullmatch(r'health_writer_network_[a-z0-9_]+',database):
        raise RuntimeError('disposable_database_name_required')
    suffix=uuid.uuid4().hex[:12]; plain='health_writer_fixture_'+suffix
    schema='health_writer_fixture_'+uuid.uuid4().hex[:12]
    login='health_writer_network_'+suffix; password=secrets.token_hex(24)
    env={k:v for k,v in os.environ.items() if k.upper() in
         {'PATH','SYSTEMROOT','WINDIR','TEMP','TMP','COMSPEC','PATHEXT','USERPROFILE','HOME','DOCKER_HOST'}}
    admin_password=os.environ.get('PGPASSWORD','')
    results=[]; schemas=[]; login_created=False
    def record(name,passed,**details):
        results.append({'name':name,'passed':bool(passed),**details})
        if not passed: raise RuntimeError('failed:'+name)
    def execute(sql,restricted=False,expected=None):
        child=env.copy();child['PGCONNECT_TIMEOUT']='10'
        child['PGPASSWORD']=password if restricted else admin_password
        role=login if restricted else 'postgres'
        if container:
            command=['docker','exec','-i','-e','PGPASSWORD','-e','PGCONNECT_TIMEOUT',container,'psql']
            if restricted:command+=['-h','127.0.0.1']
        else:command=['psql','-h','127.0.0.1']
        command+=['-X','-q','-A','-t','-v','ON_ERROR_STOP=1','-U',role,'-d',database]
        p=subprocess.run(command,input='\\set VERBOSITY verbose\n'+sql,text=True,encoding='utf-8',capture_output=True,env=child,timeout=45)
        if expected is not None:
            # Verify the actual server's error code, never a failure at SET ROLE.
            code=re.search(r'ERROR:\s+([0-9A-Z]{5}):',p.stderr)
            return p.returncode!=0 and code is not None and code[1]==expected
        if p.returncode:
            code=re.search(r'ERROR:\s+([0-9A-Z]{5}):',p.stderr)
            raise DatabaseCallError('restricted' if restricted else 'admin',code[1] if code else None)
        return p.stdout.strip()
    def checkpoint():return execute(f'SELECT {schema}.sha({schema}.checkpoint());')
    def stage(key,changes,approved=True,expired=False):
        execute(f"""DO $stage$
        DECLARE changes jsonb; b jsonb; a jsonb; payload jsonb; digest text;
        BEGIN
          changes:={changes}; b:={schema}.checkpoint(); a:=b;
          BEGIN
            PERFORM {schema}.apply_delta(changes);a:={schema}.checkpoint();
            RAISE EXCEPTION USING ERRCODE='P0099',MESSAGE='projection rollback';
          EXCEPTION WHEN SQLSTATE 'P0099' THEN NULL; END;
          payload:=jsonb_build_object('changes',changes);digest:={schema}.sha(payload);
          INSERT INTO {schema}.candidates VALUES('{key}',payload,digest,{str(approved).lower()},
            now()+interval '{'-1' if expired else '10'} minutes',{schema}.sha(b),{schema}.sha(a));
          INSERT INTO {schema}.semantic_receipts
            SELECT '{key}',id,digest,{schema}.sha(a),repeat('a',64),'PASS','SYNTHETIC ONLY',now()
            FROM unnest(ARRAY[19,20,21,22,27,28,29,30,31,37]) id;
        END $stage$;""")
    def update(title):return f"(SELECT jsonb_build_array(jsonb_build_object('table','records','action','UPDATE','key',jsonb_build_object('record_id',record_id),'expected_sha',{schema}.sha(to_jsonb(r)),'row',jsonb_build_object('title','{title}'))) FROM {schema}.records r WHERE nnn=1)"
    try:
        if not container and admin_password!='health-synthetic':
            raise RuntimeError('disposable_synthetic_admin_password_required')
        if execute("SELECT to_regclass('public.records') IS NULL;")!='t':
            raise RuntimeError('refuse_server_with_existing_public_clinical_tables')
        execute("DO $roles$ DECLARE r text; BEGIN FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role','health_test_writer_role','health_test_ci'] LOOP IF NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname=r) THEN EXECUTE format('CREATE ROLE %I NOLOGIN',r); END IF; END LOOP; END $roles$; GRANT health_test_writer_role TO health_test_ci;")
        module_spec=importlib.util.spec_from_file_location('build_fixture',HERE/'build_fixture.py')
        module=importlib.util.module_from_spec(module_spec);module_spec.loader.exec_module(module)
        catalog=json.loads((HERE/'catalog_v1.json').read_text(encoding='utf-8'))
        execute(module.render(plain,catalog));schemas.append(plain)
        old_tests='\n'.join((HERE/file).read_text(encoding='utf-8').replace('__SCHEMA__',plain) for file in ['synthetic_tests.sql','supplemental_tests.sql']).replace('SELECT name,passed,detail FROM writer_test_results ORDER BY name;','')
        old=json.loads(execute(old_tests+"\nSELECT jsonb_agg(jsonb_build_object('name',name,'passed',passed) ORDER BY name) FROM writer_test_results;"))
        record('existing_synthetic_suite',len(old)==45 and all(x['passed'] for x in old),checks=len(old),method='admin synthetic mechanics; receipts simulated')
        metadata=json.loads((HERE/'constraints_v1.json').read_text(encoding='utf-8'))
        execute(module.render(schema,catalog,metadata));schemas.append(schema)
        count=int(execute(f"SELECT count(*) FROM pg_constraint c JOIN pg_class t ON t.oid=c.conrelid JOIN pg_namespace n ON n.oid=t.relnamespace WHERE n.nspname='{schema}' AND t.relname=ANY(ARRAY["+','.join("'"+t+"'" for t in module.TABLES)+']);'))
        record('production_constraints_reproduced',count==len(metadata['constraints']),constraints=count,non_constraint_indexes=len(metadata['indexes']),scope='constraints/indexes only; production policies/triggers not reproduced')
        seed=(HERE/'synthetic_tests.sql').read_text(encoding='utf-8').split('DO $test$')[0].replace('__SCHEMA__',schema).replace("'synthetic','open','Synthetic case'","'episode','open','Synthetic case'")
        execute(seed)
        execute(f"CREATE ROLE {login} LOGIN PASSWORD '{password}' NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS; GRANT health_test_writer_role TO {login};")
        login_created=True
        who=json.loads(execute("SELECT jsonb_build_object('user',current_user,'tcp',inet_client_addr() IS NOT NULL,'super',rolsuper,'bypassrls',rolbypassrls) FROM pg_roles WHERE rolname=current_user;",True))
        record('actual_tcp_restricted_identity',who['user']==login and who['tcp'] and not who['super'] and not who['bypassrls'],authentication='SCRAM login; no SET ROLE')
        negatives={
          'direct_record_update':f"UPDATE {schema}.records SET title='bypass' WHERE nnn=1;",
          'direct_record_insert':f"INSERT INTO {schema}.records(record_id) VALUES('REC-20261011-999');",
          'direct_record_delete':f"DELETE FROM {schema}.records WHERE nnn=1;",
          'clinical_snapshot_read':f"SELECT * FROM {schema}.records;",
          'candidate_self_approval':f"UPDATE {schema}.candidates SET approved=true;",
          'semantic_receipt_forgery':f"INSERT INTO {schema}.semantic_receipts(request_key) VALUES('forged');",
          'audit_tamper':f"DELETE FROM {schema}.publish_audit;",
          'allocator_bypass':f"UPDATE {schema}.id_reservations SET state='retired';",
          'raw_delta_bypass':f"SELECT {schema}.apply_delta('[]'::jsonb);",
          'raw_checkpoint_read':f"SELECT {schema}.checkpoint();",
          'owner_escalation':'SET ROLE postgres;'
        }
        before=checkpoint()
        for name,query in negatives.items():record(name,execute(query,True,'42501'),sqlstate='42501')
        record('denials_preserve_fingerprint',checkpoint()==before)
        absent=json.loads(execute(f"SELECT {schema}.status('absent');",True))
        record('status_not_found',absent['state']=='NOT_FOUND' and set(absent)=={'state','test_only'})
        for key,approved,expired in [('missing_approval',False,False),('expired_approval',True,True)]:
            stage(key,update('blocked'),approved,expired)
            b=checkpoint();record(key,execute(f"SELECT {schema}.publish('{key}');",True,'P0001') and checkpoint()==b,sqlstate='P0001')
        stage('revoked',update('revoked'))
        execute(f"UPDATE {schema}.candidates SET approved=false WHERE request_key='revoked';")
        record('revocation_at_publish',execute(f"SELECT {schema}.publish('revoked');",True,'P0001'))
        stage('tampered',update('tampered'))
        execute(f"UPDATE {schema}.candidates SET payload=payload||jsonb_build_object('extra',true) WHERE request_key='tampered';")
        record('tampered_payload',execute(f"SELECT {schema}.publish('tampered');",True,'P0001'))
        stage('good',update('Synthetic network update'))
        result=json.loads(execute(f"SELECT {schema}.publish('good');",True))
        record('restricted_publish',result['state']=='FINALIZED' and result['replayed'] is False)
        after=checkpoint();audit=json.loads(execute(f"SELECT jsonb_build_object('count',count(*),'after_matches',bool_and(after_sha='{after}')) FROM {schema}.publish_audit WHERE request_key='good';"))
        record('atomic_audit_after_state',audit['count']==1 and audit['after_matches'])
        status=json.loads(execute(f"SELECT {schema}.status('good');",True))
        record('status_private_metadata_only',status['state']=='FINALIZED' and set(status)=={'state','operation_id','candidate_sha','after_sha','test_only'})
        replay=json.loads(execute(f"SELECT {schema}.publish('good');",True))
        record('commit_acknowledgement_reconciliation',replay['replayed'] is True and checkpoint()==after,method='actual COMMIT followed by status/replay; acknowledgement loss simulated, no fault injection')
        stage('rollback',update('never committed'))
        execute(f"BEGIN; SELECT {schema}.publish('rollback'); ROLLBACK;",True)
        record('transaction_rollback',checkpoint()==after and json.loads(execute(f"SELECT {schema}.status('rollback');",True))['state']=='CANDIDATE')
        stage('semantic_missing',update('semantic blocked'))
        execute(f"DELETE FROM {schema}.semantic_receipts WHERE request_key='semantic_missing' AND rule_id=19;")
        record('semantic_missing_over_tcp',execute(f"SELECT {schema}.publish('semantic_missing');",True,'P0001') and checkpoint()==after)
        stage('parallel_a',update('parallel A'));stage('parallel_b',update('parallel B'))
        def race(key):
            try:return json.loads(execute(f"SELECT {schema}.publish('{key}');",True))['state']
            except DatabaseCallError as e:
                if e.sqlstate!='P0001':raise
                return 'REJECTED_P0001'
        with ThreadPoolExecutor(max_workers=2) as pool: states=list(pool.map(race,['parallel_a','parallel_b']))
        record('parallel_stale_domain_rejected',sorted(states)==['FINALIZED','REJECTED_P0001'],sqlstate='P0001')
        winner='parallel_a' if states[0]=='FINALIZED' else 'parallel_b'
        stage('dependency_mutated',update('outdated'))
        execute(f"UPDATE {schema}.records SET summary='synthetic dependency change' WHERE nnn=2;")
        b=checkpoint();record('dependency_mutation',execute(f"SELECT {schema}.publish('dependency_mutated');",True,'P0001') and checkpoint()==b)
        execute(f"UPDATE {schema}.candidates SET candidate_sha=repeat('0',64) WHERE request_key='{winner}';")
        record('finalized_replay_digest_conflict',execute(f"SELECT {schema}.publish('{winner}');",True,'P0001'))
        record('real_fk_constraint_denial',execute(f"INSERT INTO {schema}.record_domains VALUES('REC-20261011-001','UNKNOWN');",expected='23503'),sqlstate='23503',method='admin tests actual reproduced FK, not omitted fixture constraints')
        return {'status':'LOCAL_TCP_COMPONENT_PASS','checks':results,'synthetic_checks':45,'extra_retired_ledger_regression':True,'production_constraints':count,'production_non_constraint_indexes':len(metadata['indexes']),'component_assertions':len(results),'actual_tcp_privilege_denials':len(negatives),'approvals':'SIMULATED','source_receipts':'SIMULATED','supabase_network_acceptance':'NOT_RUN','clinical_acceptance':'NOT_RUN','production_enablement':False}
    finally:
        for s in reversed(schemas):
            comment=execute(f"SELECT obj_description(oid,'pg_namespace') FROM pg_namespace WHERE nspname='{s}';")
            if comment!='HEALTH_SYNTHETIC_WRITER_FIXTURE_V1':raise RuntimeError('cleanup_identity_mismatch')
            execute(f'DROP SCHEMA {s} CASCADE;')
        if login_created:execute(f'DROP ROLE {login};')
        if schemas:
            remaining=execute("SELECT count(*) FROM pg_namespace WHERE nspname IN ("+','.join("'"+s+"'" for s in schemas)+');')
            if remaining!='0':raise RuntimeError('cleanup_readback_failed')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--docker-container');p.add_argument('--database',default='postgres');p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    try:
        result=run_suite(a.docker_container,a.database);result['cleanup']='schema/unique-login removed and readback verified'
        a.out.write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps({k:v for k,v in result.items() if k!='checks'}))
    except Exception as e:
        result={'status':'STOPPED','safe_reason':str(e) if isinstance(e,RuntimeError) else type(e).__name__,'production_enablement':False}
        a.out.write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result));sys.exit(2)
