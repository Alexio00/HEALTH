"""Canonical routing and restricted API tests; fresh synthetic database only.

Approval claims and semantic receipts are explicitly simulated. Never accept
a remote DB URL, production project or an existing medical database.
"""
import argparse
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import uuid
import psycopg2
import build_fixture
import build_standby

HERE=Path(__file__).resolve().parent

def run(container=None,port=5432,extra_suite=None):
    database='health_writer_standby_'+uuid.uuid4().hex[:12]
    roles=['health_standby_'+uuid.uuid4().hex[:12] for _ in range(4)]
    passwords=[secrets.token_hex(24) for _ in roles]
    checks=[]; created=False; created_roles=[]; connections=[];created_groups=False
    env=os.environ.copy(); env['PGPASSWORD']='health-synthetic'
    def admin(sql,db=database):
        command=['docker','exec','-i',container,'psql','-X','-q','-A','-t','-v','ON_ERROR_STOP=1','-U','postgres','-d',db] if container else ['psql','-h','127.0.0.1','-p',str(port),'-U','postgres','-X','-q','-A','-t','-v','ON_ERROR_STOP=1','-d',db]
        p=subprocess.run(command,input='\\set VERBOSITY verbose\n'+sql,capture_output=True,text=True,encoding='utf-8',env=env,timeout=45)
        if p.returncode:
            code=re.search(r'ERROR:\s+([A-Z0-9]{5}):',p.stderr)
            # Diagnostic is kept local; the report never includes query values.
            raise RuntimeError('standby_admin_sqlstate_'+(code[1] if code else 'UNAVAILABLE'))
        return p.stdout.strip()
    def check(name,passed):
        checks.append({'name':name,'passed':bool(passed)})
        if not passed:raise RuntimeError('failed:'+name)
    def call(role,sql,params=(),denied=None):
        try:
            with connections[role].cursor() as cur:
                cur.execute(sql,params)
                if denied:return False
                return cur.fetchone()[0] if cur.description else None
        except psycopg2.Error as e:
            if denied:return e.pgcode==denied
            raise RuntimeError('standby_sqlstate_'+(e.pgcode or 'UNAVAILABLE')) from None
    def api(role,fn,*params):
        return call(role,'SELECT health_writer.'+fn+'('+','.join(['%s']*len(params))+');',params)
    def command(key,create=False):
        value={'action':'CREATE_REC' if create else 'UPDATE','user_message_sha256':'1'*64,'conversation_ref':'synthetic-chat/command/'+key}
        if create:value['record_date']='2026-10-12'
        return api(0,'submit_intent',key,json.dumps(value))
    def authorize(key,kind,digest):
        return api(2,'accept_authorization',key,kind,digest,'308028794','1408460030','a'*40,'synthetic-'+key+'-'+kind,'1','1')
    def prepare(key,create=False):
        i=command(key,create);authorize(key,'intent',i['intent_sha']);return api(0,'prepare',key)
    def delta(title='Synthetic updated'):
        return json.loads(admin("SELECT jsonb_build_array(jsonb_build_object('table','records','action','UPDATE','key',jsonb_build_object('record_id',r.record_id),'expected_sha',health_writer.sha(to_jsonb(r)),'row',jsonb_build_object('title','"+title+"'))) FROM public.records r WHERE nnn=1;"))
    def propose(key,changes):return api(0,'propose',key,json.dumps(changes),None)
    def receipts(key,c,labs=None):
        value=[{'rule_id':i,'status':'PASS','evidence_sha':'b'*64,'methodology':'SYNTHETIC API MECHANICS ONLY'} for i in [19,20,21,22,27,28,29,30,31,37]]
        return api(3,'attest_semantics',key,c['candidate_sha'],c['after_sha'],json.dumps(value),json.dumps(labs or []))
    def digest():return admin('SELECT health_writer.sha(health_writer.checkpoint());')
    try:
        if not container and os.environ.get('PGPASSWORD')!='health-synthetic':raise RuntimeError('synthetic_admin_required')
        admin('CREATE DATABASE '+database+';',db='postgres');created=True
        admin("COMMENT ON DATABASE "+database+" IS 'HEALTH_STANDBY_SYNTHETIC_V1';")
        admin("DO $roles$ DECLARE r text; BEGIN FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role','health_test_writer_role'] LOOP IF NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname=r) THEN EXECUTE format('CREATE ROLE %I NOLOGIN',r); END IF; END LOOP; END $roles$;")
        cat=json.loads((HERE/'catalog_v1.json').read_text());cons=json.loads((HERE/'constraints_v1.json').read_text())
        schema='health_writer_fixture_'+uuid.uuid4().hex[:12]
        sql=build_fixture.render(schema,cat,cons).split('-- TEST-only delta engine.')[0]
        sql=sql.replace('CREATE SCHEMA '+schema+';','').replace('COMMENT ON SCHEMA '+schema+" IS 'HEALTH_SYNTHETIC_WRITER_FIXTURE_V1';",'')
        admin(sql.replace(schema,'public')+'COMMIT;')
        admin("CREATE TABLE public.validation_checks(check_key text PRIMARY KEY,mechanism text NOT NULL CHECK(mechanism IN ('FORMULA','OPERATION_AUDIT')),description text,dependencies text[],active boolean); CREATE TABLE public.validation_results(operation_id uuid REFERENCES public.operations(operation_id) ON DELETE CASCADE,check_key text REFERENCES public.validation_checks(check_key) ON DELETE RESTRICT,status text CHECK(status IN ('PASS','FAIL','SKIP')),checked_at timestamptz,details jsonb,PRIMARY KEY(operation_id,check_key)); ALTER TABLE public.validation_checks ENABLE ROW LEVEL SECURITY; ALTER TABLE public.validation_results ENABLE ROW LEVEL SECURITY; INSERT INTO public.validation_checks VALUES('SYNTHETIC_OLD_RULE','OPERATION_AUDIT','Existing rule',ARRAY[]::text[],true);")
        admin(build_standby.render())
        created_groups=True
        for group in ['health_writer_executor','health_writer_authorizer','health_writer_verifier']:
            admin("COMMENT ON ROLE "+group+" IS '"+database+"';")
        seed=(HERE/'synthetic_tests.sql').read_text().split('DO $test$')[0]
        seed=seed.split('INSERT INTO __SCHEMA__.expected_labs')[0]
        seed=seed.replace('__SCHEMA__','public').replace("'synthetic','open','Synthetic case'","'episode','open','Synthetic case'")
        admin(seed)
        admin("INSERT INTO public.operations(operation_id,operation,mode,scope,state,result,finalized_at) VALUES('fa39e51f-3d95-4f82-bd3b-94438e7139a1','synthetic_migration','import',ARRAY['synthetic'],'FINALIZED','PASS',clock_timestamp());")
        for role,pw,group in zip(roles,passwords,['health_writer_executor','health_writer_executor','health_writer_authorizer','health_writer_verifier']):
            admin(f"CREATE ROLE {role} LOGIN PASSWORD '{pw}' NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS; GRANT {group} TO {role};")
            created_roles.append(role)
            c=psycopg2.connect(host='127.0.0.1',port=port,user=role,password=pw,dbname=database,connect_timeout=10);c.autocommit=True;connections.append(c)
        admin(f"INSERT INTO health_writer.approval_policy VALUES(true,'{roles[2]}','308028794','1408460030',repeat('a',40)); INSERT INTO health_writer.semantic_verifier_principals VALUES('{roles[3]}'); INSERT INTO health_writer.source_verifier_principals VALUES('{roles[3]}');")
        check('default_disabled',call(0,"SELECT health_writer.submit_intent('disabled','{}');",denied='P0001'))
        admin("INSERT INTO health_writer.upload_folders VALUES('syntheticfolder123',true); UPDATE health_writer.runtime_policy SET enabled=true,code_sha=repeat('a',40),primary_folder='syntheticfolder123';")
        for name,sql in {
          'direct_public_dml':'UPDATE public.records SET title=title;',
          'self_enable':'UPDATE health_writer.runtime_policy SET enabled=true;',
          'inner_prepare':'SELECT health_writer.prepare_inner(\'x\');',
          'inner_publish':'SELECT health_writer.publish_internal(\'x\',NULL);',
          'self_authorization':'SELECT health_writer.accept_authorization(\'x\',\'intent\',NULL,NULL,NULL,NULL,NULL,NULL,NULL);',
          'self_semantics':'SELECT health_writer.attest_semantics(\'x\',NULL,NULL,\'[]\',\'[]\');',
          'audit_tamper':'DELETE FROM health_writer.publish_audit;',
          'raw_projection':'SELECT health_writer.apply_delta_internal(\'[]\',NULL);',
          'lab_context_forge':'INSERT INTO health_writer.lab_check_context VALUES(1,\'1\',\'x\',\'x\',\'x\');'
        }.items():check(name,call(0,sql,denied='42501'))
        key='canonical_update';i=command(key)
        check('unapproved_intent_cannot_read_context',call(0,'SELECT health_writer.request_context(%s);',(key,),denied='42501'))
        check('unapproved_intent_stops_prepare',call(0,'SELECT health_writer.prepare(%s);',(key,),denied='P0001'))
        authorize(key,'intent',i['intent_sha']);p=api(0,'prepare',key)
        check('owned_approved_context_available',api(0,'request_context',key)['intent_sha']==i['intent_sha'])
        check('foreign_context_denied',call(1,'SELECT health_writer.request_context(%s);',(key,),denied='42501'))
        check('canonical_operation_prepared',p['state']=='PREPARED' and admin(f"SELECT operation FROM public.operations WHERE operation_id='{p['operation_id']}';")=='HEALTH_WRITER_DELTA_V1')
        check('test_account_alias_rejected',call(0,'SELECT health_writer.plan_source(%s,%s,%s,%s);',(key,'{}','google-drive','primary'),denied='P0001'))
        snap=digest();changes=delta();c=propose(key,changes)
        check('proposal_does_not_publish',digest()==snap)
        check('foreign_candidate_denied',call(1,'SELECT health_writer.propose(%s,%s,NULL);',(key,json.dumps(changes)),denied='P0001'))
        check('candidate_replay_exact',propose(key,changes)==c)
        bad=json.loads(json.dumps(changes));bad[0]['row']['title']='different'
        check('candidate_replay_conflict',call(0,'SELECT health_writer.propose(%s,%s,NULL);',(key,json.dumps(bad)),denied='P0001'))
        check('unapproved_candidate_cannot_publish',call(0,'SELECT health_writer.finalize(%s);',(key,),denied='P0001') and digest()==snap)
        authorize(key,'candidate',c['candidate_sha'])
        check('writer_cannot_read_verifier_projection',call(0,'SELECT health_writer.review_candidate(%s);',(key,),denied='42501'))
        check('verifier_reads_exact_proposed_states',api(3,'review_candidate',key)['after_sha']==c['after_sha'])
        check('missing_semantics_cannot_publish',call(0,'SELECT health_writer.finalize(%s);',(key,),denied='P0001') and digest()==snap)
        receipts(key,c)
        result=api(0,'finalize',key)
        check('canonical_atomic_finalized',result['state']=='FINALIZED' and digest()==c['after_sha'])
        check('canonical_37_operation_bound_results',admin(f"SELECT count(*) FROM public.validation_results WHERE operation_id='{p['operation_id']}' AND details->>'candidate_sha'='{c['candidate_sha']}' AND details->>'after_sha'='{c['after_sha']}';")=='37')
        check('rendering_rule_explicit_skip_not_fabricated_pass',admin(f"SELECT status FROM public.validation_results WHERE operation_id='{p['operation_id']}' AND check_key='WRITER_V1_RULE_13';")=='SKIP')
        check('old_validation_registry_retained',admin("SELECT count(*) FROM public.validation_checks WHERE check_key='SYNTHETIC_OLD_RULE';")=='1')
        check('canonical_audit_private',admin(f"SELECT count(*) FROM health_writer.publish_audit WHERE request_key='{key}';")=='1')
        check('finalized_replay_no_second_operation',api(0,'finalize',key)['replayed'])
        check('private_controls_not_clinical_schema',admin("SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='health_writer' AND c.relname IN ('records','operations','labs');")=='0')
        key='new_canonical_rec';p=prepare(key,True)
        row=json.loads(admin('SELECT to_jsonb(r) FROM public.records r WHERE nnn=1;'))
        row.update(record_id=p['record_id'],nnn=p['nnn'],record_date='2026-10-12',title='Synthetic new REC')
        change=[{'table':'records','action':'INSERT','key':{'record_id':p['record_id']},'row':row}]
        c=propose(key,change);authorize(key,'candidate',c['candidate_sha']);receipts(key,c)
        check('allocated_rec_published',api(0,'finalize',key)['state']=='FINALIZED' and digest()==c['after_sha'])
        key='new_missing_columns';p=prepare(key,True)
        incomplete=[{'table':'records','action':'INSERT','key':{'record_id':p['record_id']},'row':{'record_id':p['record_id'],'nnn':p['nnn']}}]
        check('default_sequence_projection_blocked',call(0,'SELECT health_writer.propose(%s,%s,NULL);',(key,json.dumps(incomplete)),denied='P0001'))
        api(0,'abandon',key)
        key='lab_literal_change';prepare(key)
        changes=json.loads(admin("SELECT jsonb_build_array(jsonb_build_object('table','labs','action','UPDATE','key',jsonb_build_object('lab_id',l.lab_id),'expected_sha',health_writer.sha(to_jsonb(l)),'row',jsonb_build_object('value','1.23'))) FROM public.labs l WHERE lab_id=1;"))
        c=propose(key,changes);authorize(key,'candidate',c['candidate_sha']);receipts(key,c);snap=digest()
        check('changed_lab_requires_independent_literal',call(0,'SELECT health_writer.finalize(%s);',(key,),denied='P0001') and digest()==snap)
        literal=json.loads(admin("SELECT health_writer.lab_literal(to_jsonb(l)||jsonb_build_object('value','1.23')) FROM public.labs l WHERE lab_id=1;"))
        receipts(key,c,[{'lab_id':1,'literal_row':literal,'evidence_sha':'c'*64}])
        check('changed_lab_literal_attested',api(0,'finalize',key)['state']=='FINALIZED')
        key='backup_blocks_prepare';i=command(key);authorize(key,'intent',i['intent_sha'])
        with connections[1].cursor() as cur:cur.execute('SELECT pg_advisory_lock_shared(63741020261013);')
        check('backup_shared_lock_blocks_prepare',call(0,'SELECT health_writer.prepare(%s);',(key,),denied='P0001'))
        with connections[1].cursor() as cur:cur.execute('SELECT pg_advisory_unlock_shared(63741020261013);')
        p=api(0,'prepare',key);c=propose(key,delta('Synthetic backup coordinated'));authorize(key,'candidate',c['candidate_sha']);receipts(key,c);snap=digest()
        with connections[1].cursor() as cur:cur.execute('SELECT pg_advisory_lock_shared(63741020261013);')
        check('backup_shared_lock_blocks_publish',call(0,'SELECT health_writer.finalize(%s);',(key,),denied='P0001') and digest()==snap)
        with connections[1].cursor() as cur:cur.execute('SELECT pg_advisory_unlock_shared(63741020261013);')
        check('publish_after_backup_unlock',api(0,'finalize',key)['state']=='FINALIZED')
        # One historical exception is synthetic and local; production binding
        # is installed only from the exact owner-approved live baseline hash.
        admin("INSERT INTO public.records SELECT (jsonb_populate_record(NULL::public.records,to_jsonb(r)||jsonb_build_object('record_id','REC-20201010-910','nnn',910,'record_date','2020-10-11','title','Synthetic historical mismatch'))).* FROM public.records r WHERE nnn=1;")
        admin("INSERT INTO public.id_reservations SELECT (jsonb_populate_record(NULL::public.id_reservations,to_jsonb(i)||jsonb_build_object('nnn',910,'record_id','REC-20201010-910','state','used'))).* FROM public.id_reservations i WHERE nnn=1;")
        check('unapproved_legacy_mismatch_fails',admin('SELECT health_writer.records_schema_valid();')=='f')
        admin("INSERT INTO health_writer.legacy_record_exceptions SELECT true,record_id,health_writer.sha(to_jsonb(r)),health_writer.sha(jsonb_build_array(to_jsonb(r))),repeat('d',64),'SYNTHETIC_OWNER_EXCEPTION',true FROM public.records r WHERE nnn=910;")
        check('exact_unchanged_legacy_exception_passes',admin('SELECT health_writer.records_schema_valid();')=='t')
        check('writer_cannot_register_or_rebind_exception',call(0,"UPDATE health_writer.legacy_record_exceptions SET row_sha=repeat('a',64);",denied='42501'))
        check('writer_cannot_call_internal_exception_helper',call(0,'SELECT health_writer.records_schema_valid();',denied='42501'))
        key='legacy_preserved';prepare(key);c=propose(key,delta('Synthetic with preserved history'));authorize(key,'candidate',c['candidate_sha']);receipts(key,c)
        check('publication_preserves_exact_legacy_row',api(0,'finalize',key)['state']=='FINALIZED' and admin('SELECT health_writer.records_schema_valid();')=='t')
        check('current_audit_discloses_exact_owner_exception',admin("SELECT jsonb_array_length(v.details->'legacy_id_date_exceptions')=1 AND v.details->'legacy_id_date_exceptions'->0->>'owner_decision_ref'='SYNTHETIC_OWNER_EXCEPTION' AND (v.details->'legacy_id_date_exceptions'->0->>'unchanged')::boolean FROM public.validation_results v JOIN health_writer.prepared_requests p USING(operation_id) WHERE p.request_key='legacy_preserved' AND v.check_key='WRITER_V1_RULE_11';")=='t')
        key='legacy_change_blocked';prepare(key);snap=digest()
        changes=json.loads(admin("SELECT jsonb_build_array(jsonb_build_object('table','records','action','UPDATE','key',jsonb_build_object('record_id',r.record_id),'expected_sha',health_writer.sha(to_jsonb(r)),'row',jsonb_build_object('title','Changed historic row'))) FROM public.records r WHERE nnn=910;"))
        check('any_legacy_row_change_stops_projection',call(0,'SELECT health_writer.propose(%s,%s,NULL);',(key,json.dumps(changes)),denied='P0001') and digest()==snap)
        api(0,'abandon',key)
        check('new_unregistered_date_mismatch_fails',admin("BEGIN; INSERT INTO public.records SELECT (jsonb_populate_record(NULL::public.records,to_jsonb(r)||jsonb_build_object('record_id','REC-20201010-911','nnn',911))).* FROM public.records r WHERE nnn=910; SELECT health_writer.records_schema_valid(); ROLLBACK;")=='f')
        check('disabled_exception_fails',admin('BEGIN; UPDATE health_writer.legacy_record_exceptions SET enabled=false; SELECT health_writer.records_schema_valid(); ROLLBACK;')=='f')
        check('other_record_schema_fields_remain_strict',admin("BEGIN; UPDATE public.records SET title='' WHERE nnn=1; SELECT health_writer.records_schema_valid(); ROLLBACK;")=='f')
        check('fixing_legacy_date_invalidates_exception',admin("BEGIN; UPDATE public.records SET record_date='2020-10-10' WHERE nnn=910; SELECT health_writer.records_schema_valid(); ROLLBACK;")=='f')
        if extra_suite:
            extra_suite({'admin':admin,'check':check,'call':call,'api':api,'prepare':prepare,
              'authorize':authorize,'receipts':receipts,'digest':digest,'roles':roles,
              'passwords':passwords,'database':database,'port':port})
        key='disabled_again';prepare(key);admin('UPDATE health_writer.runtime_policy SET enabled=false;')
        check('runtime_disable_stops_existing_prepare',call(0,'SELECT health_writer.propose(%s,%s,NULL);',(key,json.dumps(delta())),denied='P0001'))
        return {'status':'LOCAL_CANONICAL_STANDBY_API_PASS','checks':checks,'assertions':len(checks),'approval_and_semantic_inputs':'SIMULATED','production_deployment':False,'production_enablement':False,'cleanup':'synthetic database and logins removed'}
    finally:
        for c in connections:c.close()
        if created:
            marker=admin("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname='"+database+"';",db='postgres')
            if marker!='HEALTH_STANDBY_SYNTHETIC_V1':raise RuntimeError('standby_cleanup_identity_mismatch')
            admin('DROP DATABASE '+database+';',db='postgres')
        for role in created_roles:admin('DROP ROLE '+role+';',db='postgres')
        # These no-login groups belong exclusively to this disposable server.
        if created_groups:
            for role in ['health_writer_executor','health_writer_authorizer','health_writer_verifier']:
                marker=admin("SELECT shobj_description(oid,'pg_authid') FROM pg_roles WHERE rolname='"+role+"';",db='postgres')
                if marker!=database:raise RuntimeError('standby_group_cleanup_identity_mismatch')
                admin('DROP ROLE '+role+';',db='postgres')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--docker-container');p.add_argument('--port',type=int,default=5432);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    try:result=run(a.docker_container,a.port)
    except Exception as e:result={'status':'STOPPED','safe_reason':str(e) if isinstance(e,RuntimeError) else type(e).__name__,'production_writes':False}
    a.out.write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result));raise SystemExit(0 if result['status']=='LOCAL_CANONICAL_STANDBY_API_PASS' else 2)
