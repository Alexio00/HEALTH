#!/usr/bin/env python3
"""Separate TCP authorization principal mechanics; signed OIDC checked separately."""
import argparse,json,secrets,sys,uuid
from pathlib import Path
from test_durable import HERE,run
from test_source_integration import document,literal

def authorization_suite(ctx):
    s=ctx['schema'];execute=ctx['execute'];check=ctx['check'];api=ctx['api']
    execute('BEGIN;'+(HERE/'approval_runtime.sql').read_text().replace('__SCHEMA__',s)+'COMMIT;')
    principal='health_authorizer_'+uuid.uuid4().hex[:12];password=secrets.token_hex(24)
    execute(f"CREATE ROLE {principal} LOGIN PASSWORD '{password}' NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;")
    index=len(ctx['roles']);ctx['roles'].append(principal);ctx['passwords'].append(password);ctx['created_roles'].append(principal)
    execute(f"GRANT USAGE ON SCHEMA {s} TO {principal}; GRANT EXECUTE ON FUNCTION {s}.accept_authorization(text,text,text,text,text,text,text,text,text) TO {principal}; INSERT INTO {s}.approval_policy VALUES(true,'{principal}','308028794','1408460030',repeat('a',40));")
    ctx['intent']('auth_intent');execute(f"UPDATE {s}.writer_intents SET approved=false WHERE request_key='auth_intent';")
    binding=json.loads(execute(f"SELECT {s}.authorization_request('auth_intent','intent');",0))
    def approve(key,kind,sha,jti='synthetic-jti-1',actor='308028794',pin='a'*40):
        return f"SELECT {s}.accept_authorization({literal(key)},{literal(kind)},{literal(sha)},{literal(actor)},'1408460030',{literal(pin)},{literal(jti)},'123456789','1');"
    sql=approve('auth_intent','intent',binding['digest'])
    check('auth_unapproved_intent_cannot_prepare',execute(f"SELECT {s}.prepare('auth_intent');",0,'P0001'))
    check('auth_writer_cannot_call_bridge',execute(sql,0,'42501'))
    check('auth_bridge_cannot_directly_mutate_clinical',execute(f"UPDATE {s}.records SET title='forbidden';",index,'42501'))
    check('auth_bridge_cannot_change_policy',execute(f"UPDATE {s}.approval_policy SET workflow_sha=repeat('b',40);",index,'42501'))
    check('auth_wrong_workflow_exact_pin_rejected',execute(approve('auth_intent','intent',binding['digest'],pin='b'*40),index,'P0001'))
    check('auth_wrong_actor_rejected',execute(approve('auth_intent','intent',binding['digest'],actor='15010426'),index,'P0001'))
    check('auth_approved_intent_has_separate_principal_receipt',json.loads(execute(sql,index))['accepted'] and execute(f"SELECT count(*) FROM {s}.approval_receipts WHERE request_key='auth_intent';")=='1')
    check('auth_intent_authorization_idempotent',json.loads(execute(sql,index))['replayed'])
    api('prepare','auth_intent');ctx['stage']('auth_intent')
    execute(f"UPDATE {s}.candidates SET approved=false WHERE request_key='auth_intent';")
    candidate=json.loads(execute(f"SELECT {s}.authorization_request('auth_intent','candidate');",0))
    before=ctx['digest']()
    check('auth_candidate_unapproved_blocks_publish',execute(f"SELECT {s}.finalize('auth_intent');",0,'P0001') and ctx['digest']()==before)
    csql=approve('auth_intent','candidate',candidate['digest'],jti='synthetic-jti-2')
    check('auth_exact_candidate_approval_and_publish',json.loads(execute(csql,index))['accepted'] and api('finalize','auth_intent')['state']=='FINALIZED')
    ctx['intent']('auth_nonce');execute(f"UPDATE {s}.writer_intents SET approved=false WHERE request_key='auth_nonce';")
    other=json.loads(execute(f"SELECT {s}.authorization_request('auth_nonce','intent');",0))
    check('auth_token_nonce_reuse_for_other_request_denied',execute(approve('auth_nonce','intent',other['digest']),index,'23505'))
    osql=approve('auth_nonce','intent',other['digest'],jti='synthetic-jti-3');execute(osql,index)
    execute(f"UPDATE {s}.writer_intents SET approved=false WHERE request_key='auth_nonce';")
    check('auth_old_receipt_does_not_restore_revoked_approval',execute(osql,index,'P0001'))
    check('auth_private_policy_and_receipts_rls',execute(f"SELECT bool_and(relrowsecurity) FROM pg_class WHERE oid IN ('{s}.approval_policy'::regclass,'{s}.approval_receipts'::regclass);")=='t')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--docker-container');p.add_argument('--database',default='postgres');p.add_argument('--out',type=Path,required=True);args=p.parse_args()
    try:
        result=run(args.docker_container,args.database,authorization_suite)
        result.update(status='LOCAL_TCP_AUTHORIZATION_BRIDGE_PASS',authorization_identity='SEPARATE_RESTRICTED_TCP_PRINCIPAL',
                      oidc_signature_network='NOT_RUN',approval_claim_inputs='SYNTHETIC_SIGNED_CLAIMS_NOT_ASSERTED',
                      cleanup='unique schemas/logins removed')
        args.out.write_text(json.dumps(result,indent=2));print(json.dumps({k:v for k,v in result.items() if k!='checks'}))
    except Exception as error:
        result={'status':'STOPPED','safe_reason':str(error) if isinstance(error,RuntimeError) else type(error).__name__,'production_enablement':False}
        args.out.write_text(json.dumps(result,indent=2));print(json.dumps(result));sys.exit(2)
