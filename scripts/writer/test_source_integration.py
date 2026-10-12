#!/usr/bin/env python3
"""SQL/byte integration on disposable PG17; approvals remain TEST simulations."""
import argparse
import json
from pathlib import Path
import secrets
import sys
import tempfile
import uuid
from source_saga import LocalProvider, ResponseLost, SagaError, digest
from test_durable import HERE, run

def literal(value):
    return "'" + value.replace("'", "''") + "'"

def document(value):
    return literal(json.dumps(value,sort_keys=True,separators=(',',':'))) + '::jsonb'

def source_suite(ctx,provider_override=None,provider_kind='LOCAL_TEST'):
    s=ctx['schema']; execute=ctx['execute']; check=ctx['check']; api=ctx['api']
    execute('BEGIN;'+(HERE/'source_runtime.sql').read_text().replace('__SCHEMA__',s)+'COMMIT;')
    verifier='health_source_verifier_'+uuid.uuid4().hex[:12]
    password=secrets.token_hex(24)
    execute(f"CREATE ROLE {verifier} LOGIN PASSWORD '{password}' NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;")
    ctx['roles'].append(verifier);ctx['passwords'].append(password);ctx['created_roles'].append(verifier)
    execute(f"GRANT USAGE ON SCHEMA {s} TO {verifier}; GRANT EXECUTE ON FUNCTION {s}.attest_source(text,text,uuid,text,text,bigint),{s}.begin_source_check(text,text) TO {verifier}; INSERT INTO {s}.source_verifier_principals VALUES('{verifier}');")
    who=json.loads(execute("SELECT jsonb_build_object('tcp',inet_client_addr() IS NOT NULL,'user',session_user,'bypass',rolbypassrls) FROM pg_roles WHERE rolname=session_user;",2))
    check('source_separate_verifier_tcp_identity',who['user']==verifier and who['tcp'] and not who['bypass'])
    for name,sql,role in [
        ('source_writer_direct_journal_dml',f"UPDATE {s}.source_uploads SET state='VERIFIED';",0),
        ('source_writer_self_attestation',f"SELECT {s}.attest_source('x','x',gen_random_uuid(),'synthetic',repeat('a',64),1);",0),
        ('source_writer_internal_finalize_bypass',f"SELECT {s}.finalize_delta('x');",0),
        ('source_verifier_clinical_dml',f"UPDATE {s}.records SET title='forbidden';",2),
        ('source_verifier_cannot_publish',f"SELECT {s}.finalize('x');",2),
        ('source_verifier_cannot_self_register',f"INSERT INTO {s}.source_verifier_principals VALUES(session_user);",2),
    ]: check(name,execute(sql,role,'42501'),sqlstate='42501')

    def status(key,sid):
        return json.loads(execute(f"SELECT {s}.source_status({literal(key)},{literal(sid)});",0))
    def plan(key,payload):
        ctx['intent'](key);op=api('prepare',key)
        source_number=int(execute(f'SELECT count(*) FROM {s}.source_uploads;'))+1
        row={'source_id':'SRC-20261012-'+str(source_number).zfill(3),'logical_path':'synthetic/'+key+'.bin','original_filename':'synthetic.bin',
             'mime_type':'application/octet-stream','size_bytes':len(payload),'sha256':digest(payload),
             'metadata':{'test_only':True},'created_at':execute('SELECT clock_timestamp();')}
        sql=f"SELECT {s}.plan_source({literal(key)},{document(row)},{literal(provider_kind)},'synthetic');"
        result=json.loads(execute(sql,0))
        check('source_'+key+'_plan_durable',result['state']=='PLANNED' and result['operation_id']==op['operation_id'])
        check('source_'+key+'_plan_replay_same_marker',json.loads(execute(sql,0))==result)
        changed=dict(row,size_bytes=len(payload)+1)
        check('source_'+key+'_plan_change_rejected',execute(f"SELECT {s}.plan_source({literal(key)},{document(changed)},{literal(provider_kind)},'synthetic');",0,'P0001'))
        execute(f"SELECT {s}.source_uncertain({literal(key)},{literal(row['source_id'])});",0)
        check('source_'+key+'_uncertain_durable',status(key,row['source_id'])['state']=='UNCERTAIN')
        return row,result

    def stage(key,row,planned,object_id):
        instant=execute('SELECT clock_timestamp();')
        location={'source_id':row['source_id'],'provider':provider_kind,'account_alias':'synthetic',
                  'provider_object_id':object_id,'location_role':'PRIMARY','created_at':instant,'verified_at':instant}
        manifest={'source_id':row['source_id'],'marker':planned['marker'],'source_row':row,
                  'provider':provider_kind,'account_alias':'synthetic','object_id':object_id,'location_row':location}
        changes=[{'table':'sources','action':'INSERT','key':{'source_id':row['source_id']},'row':row},
                 {'table':'source_locations','action':'INSERT','key':{k:location[k] for k in
                   ('source_id','provider','account_alias','provider_object_id','location_role')},'row':location},
                 {'table':'record_sources','action':'INSERT','key':{'record_id':'REC-20261011-001','source_id':row['source_id'],'role':'evidence'},
                  'row':{'record_id':'REC-20261011-001','source_id':row['source_id'],'role':'evidence','provenance':{'test_only':True}}}]
        execute(f"""DO $stage$ DECLARE b jsonb; a jsonb; payload jsonb; op uuid; binding text; candidate text;
         BEGIN SELECT operation_id,intent_sha INTO op,binding FROM {s}.prepared_requests WHERE request_key={literal(key)};
          b:={s}.checkpoint();
          BEGIN PERFORM {s}.apply_delta_internal({document(changes)},op); a:={s}.checkpoint();
           RAISE EXCEPTION USING ERRCODE='P0099',MESSAGE='projection rollback';
          EXCEPTION WHEN SQLSTATE 'P0099' THEN NULL; END;
          payload:=jsonb_build_object('changes',{document(changes)},'intent_sha',binding,'source_manifest',{document([manifest])});
          candidate:={s}.sha(payload);
          INSERT INTO {s}.candidates VALUES({literal(key)},payload,candidate,true,clock_timestamp()+interval '10 minutes',{s}.sha(b),{s}.sha(a));
          INSERT INTO {s}.semantic_receipts SELECT {literal(key)},id,candidate,{s}.sha(a),repeat('a',64),'PASS','SYNTHETIC ONLY',clock_timestamp() FROM unnest(ARRAY[19,20,21,22,27,28,29,30,31,37]) id;
         END $stage$;""")
        return manifest

    def attest(key,row,planned,provider,manifest):
        execute(f"SELECT {s}.begin_source_check({literal(key)},{literal(row['source_id'])});",2)
        objects=provider.find(planned['marker'])
        if len(objects)!=1: raise SagaError('ambiguous_correlation_marker')
        obj=objects[0]
        metadata,sha,size=provider.readback(obj['object_id'])
        if (metadata.get('marker')!=planned['marker'] or metadata.get('source_id')!=row['source_id']
                or obj['object_id']!=manifest['object_id']): raise SagaError('readback_identity_mismatch')
        return json.loads(execute(f"SELECT {s}.attest_source({literal(key)},{literal(row['source_id'])},{literal(planned['marker'])}::uuid,{literal(obj['object_id'])},{literal(sha)},{size});",2))

    with tempfile.TemporaryDirectory(prefix='health-source-integrated-') as tmp:
        provider=provider_override or LocalProvider(Path(tmp)/'provider');payload=b'SYNTHETIC SQL SOURCE INTEGRATION\x00\xff\n'
        row,planned=plan('source_lost',payload)
        check('source_marker_exists_before_external_create',not provider.find(planned['marker']))
        try: provider.create(planned['marker'],row['source_id'],payload,lose_reply=True)
        except ResponseLost: pass
        objects=provider.find(planned['marker'])
        check('source_actual_upload_lost_reply',len(objects)==1 and status('source_lost',row['source_id'])['state']=='UNCERTAIN')
        manifest=stage('source_lost',row,planned,objects[0]['object_id']);before=ctx['digest']()
        check('source_missing_attestation_blocks_atomic_publish',execute(f"SELECT {s}.finalize('source_lost');",0,'P0001') and ctx['digest']()==before)
        check('source_foreign_writer_status_denied',execute(f"SELECT {s}.source_status('source_lost',{literal(row['source_id'])});",1,'42501'))
        check('source_independent_actual_bytes_attested',attest('source_lost',row,planned,provider,manifest)['state']=='VERIFIED')
        execute(f"UPDATE {s}.source_uploads SET checked_at=clock_timestamp()-interval '11 minutes' WHERE request_key='source_lost';")
        check('source_stale_attestation_blocks_publish',execute(f"SELECT {s}.finalize('source_lost');",0,'P0001') and ctx['digest']()==before)
        attest('source_lost',row,planned,provider,manifest)
        original=execute(f"SELECT payload::text FROM {s}.candidates WHERE request_key='source_lost';")
        execute(f"UPDATE {s}.candidates SET payload=jsonb_set(payload,'{{source_manifest,0,object_id}}','\"wrong_object_identity\"'::jsonb),candidate_sha={s}.sha(jsonb_set(payload,'{{source_manifest,0,object_id}}','\"wrong_object_identity\"'::jsonb)) WHERE request_key='source_lost';")
        check('source_candidate_mutation_invalidates_attestation',execute(f"SELECT {s}.finalize('source_lost');",0,'P0001') and ctx['digest']()==before)
        execute(f"UPDATE {s}.candidates SET payload={literal(original)}::jsonb,candidate_sha={s}.sha({literal(original)}::jsonb) WHERE request_key='source_lost';")
        result=api('finalize','source_lost')
        check('source_atomic_publication_and_journal_transition',result['state']=='FINALIZED' and status('source_lost',row['source_id'])['state']=='PUBLISHED'
              and execute(f"SELECT count(*) FROM {s}.sources WHERE source_id={literal(row['source_id'])};")=='1'
              and execute(f"SELECT count(*) FROM {s}.record_sources WHERE source_id={literal(row['source_id'])};")=='1')
        check('source_exact_after_state_readback',execute(f"SELECT after_sha={s}.sha({s}.checkpoint()) FROM {s}.publish_audit WHERE request_key='source_lost';")=='t')
        check('source_replay_without_duplicate_object_or_rows',api('finalize','source_lost')['replayed'] and len(provider.find(planned['marker']))==1)
        partial,pp=plan('source_partial',payload)
        try: provider.create(pp['marker'],partial['source_id'],payload,partial=True)
        except ResponseLost: pass
        pm=stage('source_partial',partial,pp,provider.find(pp['marker'])[0]['object_id']);before=ctx['digest']()
        check('source_partial_byte_readback_blocks_journal',attest('source_partial',partial,pp,provider,pm)['state']=='BLOCKED' and status('source_partial',partial['source_id'])['state']=='BLOCKED')
        check('source_partial_cannot_publish_or_retry',execute(f"SELECT {s}.finalize('source_partial');",0,'P0001') and execute(f"SELECT {s}.source_uncertain('source_partial',{literal(partial['source_id'])});",0,'P0001') and ctx['digest']()==before)
        api('abandon','source_partial')
        check('source_abandon_preserves_partial_orphan',len(provider.find(pp['marker']))==1 and status('source_partial',partial['source_id'])['state']=='BLOCKED')
        changed,cp=plan('source_changed',payload)
        oid=provider.create(cp['marker'],changed['source_id'],payload)
        cm=stage('source_changed',changed,cp,oid);attest('source_changed',changed,cp,provider,cm)
        if provider_override is None:
            (provider.root/oid/'bytes').write_bytes(b'SYNTHETIC CHANGED BYTES')
        else:
            provider.replace_created_for_test(oid,b'SYNTHETIC CHANGED BYTES')
        try:
            mutated=attest('source_changed',changed,cp,provider,cm)['state']=='BLOCKED'
        except SagaError as error:
            if str(error)!='provider_changed_during_readback': raise
            mutated=status('source_changed',changed['source_id'])['state']=='UNCERTAIN'
        check('source_recheck_detects_mutated_verified_object',mutated)
        before=ctx['digest']()
        check('source_mutation_prevents_publication',execute(f"SELECT {s}.finalize('source_changed');",0,'P0001') and ctx['digest']()==before)
        api('abandon','source_changed')
        check('source_all_private_tables_rls',execute(f"SELECT bool_and(relrowsecurity) FROM pg_class WHERE oid IN ('{s}.source_uploads'::regclass,'{s}.source_verifier_principals'::regclass);")=='t')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--docker-container');parser.add_argument('--database',default='postgres');parser.add_argument('--out',type=Path,required=True);args=parser.parse_args()
    try:
        result=run(args.docker_container,args.database,source_suite)
        result.update(status='LOCAL_TCP_SQL_SOURCE_INTEGRATION_PASS',source_saga='SQL_JOURNAL_ATOMIC_PUBLICATION_ACTUAL_SYNTHETIC_BYTES',
                      independent_verifier_identity='SEPARATE_RESTRICTED_DATABASE_LOGIN_OVER_TCP',
                      provider='DISPOSABLE_LOCAL_FILESYSTEM',provider_acl_retention='NOT_ACCEPTED',
                      source_external_mutation_race='RECHECK_TESTED_NOT_PROVIDER_IMMUTABILITY',
                      cleanup='unique schemas/logins and synthetic provider removed')
        args.out.write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in result.items() if k!='checks'}))
    except Exception as error:
        result={'status':'STOPPED','safe_reason':str(error) if isinstance(error,RuntimeError) else type(error).__name__,'production_enablement':False}
        args.out.write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result));sys.exit(2)
