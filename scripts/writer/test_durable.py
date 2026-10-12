#!/usr/bin/env python3
"""Real disposable PG17 TCP tests for durable synthetic preparation/publication.

Intents, candidate approvals and semantic receipts remain administrator simulations.
No Supabase URL, secret, clinical data or production schema is accepted.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import uuid
import build_fixture

HERE = Path(__file__).resolve().parent

class CallError(RuntimeError):
    def __init__(self, code, constraint=None):
        self.code = code
        super().__init__('sqlstate:' + (code or 'UNAVAILABLE') + ((';constraint:' + constraint) if constraint else ''))

def run(container=None, database='postgres', extra_suite=None):
    if database != 'postgres' and not re.fullmatch(r'health_writer_durable_[a-z0-9_]+', database):
        raise RuntimeError('disposable_database_required')
    schema = 'health_writer_fixture_' + uuid.uuid4().hex[:12]
    roles = ['health_writer_durable_' + uuid.uuid4().hex[:12] for _ in range(2)]
    passwords = [secrets.token_hex(24) for _ in roles]
    env = {k:v for k,v in os.environ.items() if k.upper() in
           {'PATH','SYSTEMROOT','WINDIR','TEMP','TMP','COMSPEC','PATHEXT','HOME','USERPROFILE','DOCKER_HOST'}}
    admin_password = os.environ.get('PGPASSWORD', '')
    created = False
    created_roles = []
    checks = []
    def execute(sql, role=None, expected=None):
        child = env.copy()
        child['PGPASSWORD'] = passwords[role] if role is not None else admin_password
        child['PGCONNECT_TIMEOUT'] = '10'
        user = roles[role] if role is not None else 'postgres'
        command = ['docker','exec','-i','-e','PGPASSWORD','-e','PGCONNECT_TIMEOUT',container,'psql'] if container else ['psql']
        if role is not None or not container:
            command += ['-h','127.0.0.1']
        command += ['-X','-q','-A','-t','-v','ON_ERROR_STOP=1','-U',user,'-d',database]
        p = subprocess.run(command, input='\\set VERBOSITY verbose\n'+sql,
                           text=True, encoding='utf-8', capture_output=True, env=child, timeout=45)
        code = re.search(r'ERROR:\s+([0-9A-Z]{5}):', p.stderr)
        code = code[1] if code else None
        if expected:
            return p.returncode != 0 and code == expected
        if p.returncode:
            constraint = re.search(r'CONSTRAINT NAME:\s+([a-zA-Z_][a-zA-Z0-9_]*)', p.stderr)
            raise CallError(code, constraint[1] if constraint else None)
        return p.stdout.strip()
    def check(name, passed, **details):
        checks.append({'name': name, 'passed': bool(passed), **details})
        if not passed:
            raise RuntimeError('failed:' + name)
    def api(fn, key, role=0):
        return json.loads(execute(f"SELECT {schema}.{fn}('{key}');", role))
    def digest():
        return execute(f'SELECT {schema}.sha({schema}.checkpoint());')
    def intent(key, create=False, role=0):
        value = "jsonb_build_object('action','CREATE_REC','record_date','2026-10-12')" if create else "jsonb_build_object('action','UPDATE')"
        execute(f"INSERT INTO {schema}.writer_intents VALUES('{key}','{roles[role]}',{value},{schema}.sha({value}),true,clock_timestamp()+interval '10 minutes');")
    def stage(key, create=False):
        if create:
            changes = f"""(SELECT jsonb_build_array(jsonb_build_object('table','records','action','INSERT',
             'key',jsonb_build_object('record_id',p.proposed_record_id),'row',
              to_jsonb(r)||jsonb_build_object('record_id',p.proposed_record_id,'nnn',p.nnn,'record_date','2026-10-12','title','Synthetic newly allocated REC')))
             FROM {schema}.records r CROSS JOIN {schema}.prepared_requests p WHERE r.nnn=1 AND p.request_key='{key}')"""
        else:
            changes = f"""(SELECT jsonb_build_array(jsonb_build_object('table','records','action','UPDATE',
             'key',jsonb_build_object('record_id',r.record_id),'expected_sha',{schema}.sha(to_jsonb(r)),
             'row',jsonb_build_object('title','Synthetic durable {key}'))) FROM {schema}.records r WHERE nnn=1)"""
        execute(f"""DO $stage$ DECLARE changes jsonb; b jsonb; a jsonb; payload jsonb; op uuid;
         pinned_time timestamptz:=clock_timestamp(); binding text; candidate text;
        BEGIN
         SELECT operation_id,intent_sha INTO op,binding FROM {schema}.prepared_requests WHERE request_key='{key}';
         changes:={changes}; b:={schema}.checkpoint();
         BEGIN
          PERFORM {schema}.apply_delta_internal(changes,op);
          UPDATE {schema}.id_reservations SET state='used',record_id=metadata->>'proposed_record_id',updated_at=pinned_time WHERE operation_id=op AND state='reserved';
          a:={schema}.checkpoint(); RAISE EXCEPTION USING ERRCODE='P0099',MESSAGE='projection rollback';
         EXCEPTION WHEN SQLSTATE 'P0099' THEN NULL; END;
         payload:=jsonb_build_object('changes',changes,'intent_sha',binding,'ledger_updated_at',pinned_time);
         candidate:={schema}.sha(payload);
         INSERT INTO {schema}.candidates VALUES('{key}',payload,candidate,true,clock_timestamp()+interval '10 minutes',{schema}.sha(b),{schema}.sha(a));
         INSERT INTO {schema}.semantic_receipts SELECT '{key}',id,candidate,{schema}.sha(a),repeat('a',64),'PASS','SYNTHETIC ONLY',clock_timestamp() FROM unnest(ARRAY[19,20,21,22,27,28,29,30,31,37]) id;
        END $stage$;""")
    try:
        if not container and admin_password != 'health-synthetic':
            raise RuntimeError('disposable_admin_required')
        if execute("SELECT to_regclass('public.records') IS NULL;") != 't':
            raise RuntimeError('refuse_existing_public_clinical_tables')
        execute("DO $roles$ DECLARE r text; BEGIN FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role','health_test_writer_role'] LOOP IF NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname=r) THEN EXECUTE format('CREATE ROLE %I NOLOGIN',r); END IF; END LOOP; END $roles$;")
        catalog = json.loads((HERE/'catalog_v1.json').read_text())
        constraints = json.loads((HERE/'constraints_v1.json').read_text())
        execute(build_fixture.render(schema,catalog,constraints))
        created = True
        execute('BEGIN;'+(HERE/'durable_runtime.sql').read_text().replace('__SCHEMA__',schema)+'COMMIT;')
        seed = (HERE/'synthetic_tests.sql').read_text().split('DO $test$')[0].replace('__SCHEMA__',schema).replace("'synthetic','open','Synthetic case'","'episode','open','Synthetic case'")
        execute(seed)
        for role, password in zip(roles,passwords):
            execute(f"CREATE ROLE {role} LOGIN PASSWORD '{password}' NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS; GRANT health_test_writer_role TO {role};")
            created_roles.append(role)
        who = json.loads(execute("SELECT jsonb_build_object('user',current_user,'tcp',inet_client_addr() IS NOT NULL,'super',rolsuper,'bypass',rolbypassrls) FROM pg_roles WHERE rolname=current_user;",0))
        check('restricted_tcp_identity',who['user']==roles[0] and who['tcp'] and not who['super'] and not who['bypass'])
        for name, sql in {
            'intent_self_approval':f"UPDATE {schema}.writer_intents SET approved=true;",
            'prepared_binding_tamper':f"DELETE FROM {schema}.prepared_requests;",
            'direct_allocator':f"INSERT INTO {schema}.id_reservations(nnn,state) VALUES(900,'retired');",
            'internal_publish_bypass':f"SELECT {schema}.publish_internal('x',NULL);",
            'legacy_publish_bypass':f"SELECT {schema}.publish('x');",
            'raw_delta_bypass':f"SELECT {schema}.apply_delta_internal('[]',NULL);",
            'validation_forgery':f"DELETE FROM {schema}.writer_validation_results;",
            'revision_delete':f"DELETE FROM {schema}.publish_audit;",
            'clinical_dml':f"UPDATE {schema}.records SET title='forbidden';"
        }.items():
            check(name,execute(sql,0,'42501'),sqlstate='42501')
        intent('new',create=True)
        before = execute(f"SELECT count(*) FROM {schema}.records;")
        p = api('prepare','new')
        check('durable_prepared_and_no_medical_publish',p['state']=='PREPARED' and before==execute(f"SELECT count(*) FROM {schema}.records;") and execute(f"SELECT state FROM {schema}.id_reservations WHERE nnn={p['nnn']};")=='reserved')
        check('prepare_resume_same_operation',api('prepare','new')==p)
        check('foreign_caller_status_denied',execute(f"SELECT {schema}.request_status('new');",1,'42501'),sqlstate='42501')
        check('foreign_caller_finalize_denied',execute(f"SELECT {schema}.finalize('new');",1,'42501'),sqlstate='42501')
        intent('blocked')
        check('competing_prepared_rejected',execute(f"SELECT {schema}.prepare('blocked');",0,'23505'),sqlstate='23505')
        check('failed_prepare_does_not_create_operation',execute(f"SELECT count(*) FROM {schema}.prepared_requests WHERE request_key='blocked';")=='0')
        stage('new',create=True)
        result = api('finalize','new')
        check('create_atomic_used_and_finalized',result['state']=='FINALIZED' and api('request_status','new')['operation_id']==p['operation_id'] and execute(f"SELECT state||'|'||record_id FROM {schema}.id_reservations WHERE nnn={p['nnn']};")=='used|'+p['record_id'])
        check('operation_bound_validation_journal',execute(f"SELECT count(*) FROM {schema}.writer_validation_results WHERE operation_id='{p['operation_id']}';")=='30')
        check('finalized_replay_same_operation',api('finalize','new')['replayed'] and api('prepare','new')['operation_id']==p['operation_id'])
        check('finalized_cannot_abandon',execute(f"SELECT {schema}.abandon('new');",0,'P0001'),sqlstate='P0001')
        intent('retire',create=True); r = api('prepare','retire'); b = digest()
        check('durable_abandon',api('abandon','retire')['state']=='FAILED' and execute(f"SELECT state FROM {schema}.id_reservations WHERE nnn={r['nnn']};")=='retired')
        check('abandon_replay_no_new_allocation',api('abandon','retire')['nnn']==r['nnn'] and api('prepare','retire')['state']=='FAILED')
        intent('next',create=True); n = api('prepare','next')
        check('retired_nnn_never_reused',n['nnn']>r['nnn'])
        stage('next',create=True); snap=digest()
        execute(f"DELETE FROM {schema}.semantic_receipts WHERE request_key='next' AND rule_id=19;")
        check('failed_publish_keeps_prepared_reservation',execute(f"SELECT {schema}.finalize('next');",0,'P0001') and digest()==snap and api('request_status','next')['state']=='PREPARED' and execute(f"SELECT state FROM {schema}.id_reservations WHERE nnn={n['nnn']};")=='reserved')
        api('abandon','next')
        intent('rollback',create=True)
        ledger_before = execute(f'SELECT count(*) FROM {schema}.id_reservations;')
        execute(f"BEGIN; SELECT {schema}.prepare('rollback'); ROLLBACK;",0)
        check('rolled_back_reservation_is_not_retired',execute(f'SELECT count(*) FROM {schema}.id_reservations;')==ledger_before and api('request_status','rollback')['state']=='NOT_PREPARED')
        intent('binding'); bp=api('prepare','binding'); stage('binding')
        execute(f"UPDATE {schema}.writer_intents SET intent_sha=repeat('0',64) WHERE request_key='binding';")
        check('intent_mutation_blocks_publish',execute(f"SELECT {schema}.finalize('binding');",0,'P0001') and api('request_status','binding')['state']=='PREPARED')
        api('abandon','binding')
        intent('foreign_class'); cp=api('prepare','foreign_class'); stage('foreign_class')
        execute(f"UPDATE {schema}.operations SET operation='full_migration' WHERE operation_id='{cp['operation_id']}';")
        check('migration_operation_class_rejected',execute(f"SELECT {schema}.finalize('foreign_class');",0,'P0001'))
        check('migration_operation_abandon_rejected',execute(f"SELECT {schema}.abandon('foreign_class');",0,'P0001'))
        execute(f"UPDATE {schema}.operations SET operation='SYNTHETIC_DURABLE_DELTA' WHERE operation_id='{cp['operation_id']}';")
        api('abandon','foreign_class')
        intent('expired')
        execute(f"UPDATE {schema}.writer_intents SET expires_at=clock_timestamp()-interval '1 minute' WHERE request_key='expired';")
        check('expired_intent_cannot_prepare',execute(f"SELECT {schema}.prepare('expired');",0,'P0001') and api('request_status','expired')['state']=='NOT_PREPARED')
        intent('revoke'); api('prepare','revoke'); stage('revoke'); snap=digest()
        execute(f"UPDATE {schema}.writer_intents SET approved=false WHERE request_key='revoke';")
        check('revoked_intent_cannot_publish',execute(f"SELECT {schema}.finalize('revoke');",0,'P0001') and digest()==snap)
        api('abandon','revoke')
        intent('candidate_revoke'); api('prepare','candidate_revoke'); stage('candidate_revoke'); snap=digest()
        execute(f"UPDATE {schema}.candidates SET approved=false WHERE request_key='candidate_revoke';")
        check('revoked_exact_candidate_cannot_publish',execute(f"SELECT {schema}.finalize('candidate_revoke');",0,'P0001') and digest()==snap)
        api('abandon','candidate_revoke')
        intent('race_a',create=True); intent('race_b',create=True)
        def race(key):
            try: return api('prepare',key)['state']
            except CallError as e:
                if e.code != '23505': raise
                return 'REJECTED_23505'
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes=list(pool.map(race,['race_a','race_b']))
        check('parallel_prepare_one_winner',sorted(outcomes)==['PREPARED','REJECTED_23505'])
        api('abandon','race_a' if outcomes[0]=='PREPARED' else 'race_b')
        if extra_suite is not None:
            extra_suite({'schema':schema,'execute':execute,'check':check,'api':api,
                         'intent':intent,'stage':stage,'digest':digest,'roles':roles,
                         'passwords':passwords,'created_roles':created_roles})
        execute(f"INSERT INTO {schema}.id_reservations(nnn,state) VALUES(999,'retired');")
        intent('exhausted',create=True)
        check('nnn_exhaustion_no_durable_operation',execute(f"SELECT {schema}.prepare('exhausted');",0,'P0001') and api('request_status','exhausted')['state']=='NOT_PREPARED')
        return {'status':'LOCAL_TCP_DURABLE_WRITER_PASS','checks':checks,'assertions':len(checks),
                'approval_and_semantic_inputs':'SIMULATED','production_enablement':False,
                'supabase_network_acceptance':'NOT_RUN','source_saga':'NOT_IMPLEMENTED_BY_THIS_OVERLAY',
                'canonical_validation_catalog':'NOT_INTEGRATED','cleanup':'pending'}
    finally:
        if created:
            marker=execute(f"SELECT obj_description(oid,'pg_namespace') FROM pg_namespace WHERE nspname='{schema}';")
            if marker!='HEALTH_SYNTHETIC_WRITER_FIXTURE_V1': raise RuntimeError('cleanup_identity_mismatch')
            execute(f'DROP SCHEMA {schema} CASCADE;')
        for role in created_roles:
            execute(f'DROP ROLE {role};')
        if created and execute(f"SELECT count(*) FROM pg_namespace WHERE nspname='{schema}';")!='0':
            raise RuntimeError('cleanup_readback_failed')

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--docker-container'); parser.add_argument('--database',default='postgres')
    parser.add_argument('--out',type=Path,required=True); args=parser.parse_args()
    try:
        result=run(args.docker_container,args.database)
        result['cleanup']='unique schema/logins removed; schema readback verified'
        args.out.write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps({k:v for k,v in result.items() if k!='checks'}))
    except Exception as error:
        result={'status':'STOPPED','safe_reason':str(error) if isinstance(error,RuntimeError) else type(error).__name__,'production_enablement':False}
        args.out.write_text(json.dumps(result,indent=2),encoding='utf-8'); print(json.dumps(result)); sys.exit(2)
