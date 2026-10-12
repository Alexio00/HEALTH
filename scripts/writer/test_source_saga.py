#!/usr/bin/env python3
"""Durable local-provider tests with real synthetic bytes; no external services."""
import argparse
import json
from pathlib import Path
import tempfile
import uuid
from source_saga import Journal, LocalProvider, ResponseLost, SagaError, digest

def suite(root):
    checks=[]
    def check(name,ok):
        checks.append({'name':name,'passed':bool(ok)})
        if not ok: raise RuntimeError('failed:'+name)
    def denied(fn,reason):
        try: fn()
        except SagaError as error: return str(error)==reason
        return False
    with tempfile.TemporaryDirectory(prefix='source-saga-synthetic-',dir=root) as tmp:
        base=Path(tmp); provider=LocalProvider(base/'provider'); path=base/'journal.sqlite'
        journal=Journal(path); payload=b'SYNTHETIC SOURCE ONLY\x00\xff\n'
        op=str(uuid.uuid4()); sha='a'*64; sid=str(uuid.uuid4())
        planned=journal.plan('lost',op,sha,sid,digest(payload),len(payload))
        check('durable_marker_before_external_call',planned['state']=='PLANNED' and not provider.find(planned['marker']))
        check('idempotent_plan_preserves_source_and_marker',journal.plan('lost',op,sha,sid,digest(payload),len(payload))==planned)
        check('candidate_change_rejected',denied(lambda:journal.plan('lost',op,'b'*64,sid,digest(payload),len(payload)),'idempotency_binding_conflict'))
        check('preupload_bytes_mismatch_no_object',denied(lambda:journal.upload('lost',provider,b'wrong'),'candidate_bytes_mismatch_before_upload') and not provider.find(planned['marker']))
        check('actual_created_object_reply_lost',denied(lambda:journal.upload('lost',provider,payload,lose_reply=True),'upload_reply_lost') and len(provider.find(planned['marker']))==1)
        journal.close(); journal=Journal(path)
        check('uncertain_state_survives_process_restart',journal.get('lost')['state']=='UNCERTAIN')
        recovered=journal.reconcile('lost',provider)
        check('actual_bytes_readback_reconciles_lost_reply',recovered['state']=='VERIFIED' and recovered['source_id']==sid)
        check('replay_does_not_create_duplicate',journal.upload('lost',provider,payload)['object_id']==recovered['object_id'] and len(provider.find(planned['marker']))==1)
        receipt=journal.receipt('lost',op,sha,provider)
        check('receipt_binds_identity_bytes_operation_candidate',receipt['source_id']==sid and receipt['object_id']==recovered['object_id'] and receipt['expected_sha']==digest(payload) and receipt['size_bytes']==len(payload))
        check('receipt_foreign_operation_denied',denied(lambda:journal.receipt('lost',str(uuid.uuid4()),sha,provider),'receipt_operation_candidate_mismatch'))
        partial=journal.plan('partial',op,sha,str(uuid.uuid4()),digest(payload),len(payload))
        check('interrupted_upload_remains_discoverable',denied(lambda:journal.upload('partial',provider,payload,partial=True),'upload_reply_lost') and len(provider.find(partial['marker']))==1)
        check('partial_bytes_block_publication',denied(lambda:journal.receipt('partial',op,sha,provider),'source_digest_or_length_mismatch') and journal.get('partial')['state']=='BLOCKED')
        check('blocked_upload_not_silently_overwritten',denied(lambda:journal.upload('partial',provider,payload),'upload_not_recoverable_automatically') and len(provider.find(partial['marker']))==1)
        ambiguous=journal.plan('ambiguous',op,sha,str(uuid.uuid4()),digest(payload),len(payload))
        provider.create(ambiguous['marker'],ambiguous['source_id'],payload)
        provider.create(ambiguous['marker'],ambiguous['source_id'],payload)
        check('same_hash_two_identities_fail_closed',denied(lambda:journal.reconcile('ambiguous',provider),'ambiguous_correlation_marker'))
        check('abandon_preserves_orphan_objects',journal.abandon('ambiguous')['state']=='ABANDONED' and len(provider.find(ambiguous['marker']))==2)
        (provider.root/recovered['object_id']/'bytes').write_bytes(b'SYNTHETIC MUTATION')
        check('verified_primary_mutation_detected_on_next_readback',denied(lambda:journal.receipt('lost',op,sha,provider),'source_digest_or_length_mismatch'))
        journal.close()
    return {'status':'LOCAL_BYTE_SOURCE_SAGA_COMPONENT_PASS','checks':checks,'assertions':len(checks),
            'actual_synthetic_byte_readback':True,'upload_reply_loss':'REAL_ADAPTER_CREATED_OBJECT_THEN_DROPPED_REPLY',
            'provider':'DISPOSABLE_LOCAL_FILESYSTEM','provider_acl_retention':'NOT_ACCEPTED',
            'independent_verifier_identity':'NOT_PROVEN','sql_writer_source_integration':'NOT_IMPLEMENTED',
            'production_enablement':False,'cleanup':'temporary synthetic journal/provider removed'}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    result=suite(a.out.resolve().parent)
    a.out.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='checks'}))
