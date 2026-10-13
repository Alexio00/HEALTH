"""Full candidate, full activation, then daily DB/Auth+all-byte verification.

Use only from the reviewed exact-head workflow with a shared concurrency group.
Failed/unfinished candidates survive for exact-ID reconciliation. No permanent
delete, source purge, migration finalization or project cutover is performed.
"""
import argparse,hashlib,json,os,re
from pathlib import Path
from complete_archive import digest
from complete_sources import SourceStop,private
from complete_preview import preview,SEED_FOLDER,SEED_FILE,SEED_SHA
from complete_cloud import CompleteCloud
from complete_recovery import recover_archive
from drive_cloud_journal import DriveCloudJournal
from drive_rotation import DriveRotation,RotationStop
from cutover_guard import CutoverStop, require_release_context

EXECUTORS=['complete_archive.py','complete_capture.py','complete_coordination.py','complete_sources.py','complete_payload.py','complete_db_restore.py','complete_auth_restore.py','complete_source_restore.py','complete_recovery.py','complete_preview.py','complete_cloud.py','complete_pipeline.py','drive_rotation.py','drive_cloud_journal.py','drive_transport.py','session_pooler_tls.py','cutover_guard.py']
def executor_binding():
    pins={x:digest(Path(__file__).with_name(x)) for x in EXECUTORS}
    return hashlib.sha256(json.dumps(pins,sort_keys=True,separators=(',',':')).encode()).hexdigest(),pins

def require_candidate_binding(props, producer_sha, archive_sha):
    if (not isinstance(props,dict)
            or props.get('health_complete_set')!='v1'
            or props.get('health_pipeline_commit')!=producer_sha
            or props.get('health_archive_sha256')!=archive_sha
            or props.get('health_recovery_state') not in ('CANDIDATE','ACTIVE')):
        raise SourceStop('candidate_producer_sha_or_archive_binding_mismatch')

def retire_bootstrap(*unused):
    # Historical bootstrap was already retired; never touch old Drive IDs.
    return 0

def run(mode,root,producer_sha,*,serialized):
    if serialized is not True or mode not in ('candidate','activate','daily') or not re.fullmatch('[a-f0-9]{40}',producer_sha):raise SourceStop('reviewed_serialized_pipeline_required')
    if mode in ('candidate','activate'):
        require_release_context(os.environ,mode)
    root=private(root,fresh=True);executor_sha,pins=executor_binding()
    (root/'executor-binding.private.json').write_text(json.dumps({'producer_sha':producer_sha,'executor_sha':executor_sha,'files':pins},indent=2))
    config=os.environ['RCLONE_CONFIG_CONTENT']
    cloud_root=root/'cloud';cloud_root.mkdir(mode=0o700)
    cloud=CompleteCloud(config,cloud_root);journal=None
    try:
        parent=cloud.meta(cloud.parent);activation=parent.get('appProperties',{})
        if mode=='daily' and (activation.get('health_backup_pipeline')!='v1' or activation.get('health_recovery_executor')!=executor_sha):raise SourceStop('current_executor_full_activation_required')
        journal=DriveCloudJournal(cloud.t,cloud.parent,root/'worker-lock.sqlite',serialized=True)
        pending=journal.read()
        candidates=[x for x in cloud.children(cloud.parent) if x.get('appProperties',{}).get('health_complete_set')=='v1' and x.get('appProperties',{}).get('health_recovery_state')=='CANDIDATE']
        if pending and pending['state']!='DONE':
            target=pending['target'];sha=pending['sha']
            if mode=='candidate':raise SourceStop('pending_rotation_requires_activation_or_daily_reconciliation')
        elif candidates:
            if len(candidates)!=1:raise SourceStop('multiple_pending_candidates_require_exact_reconciliation')
            target=candidates[0]['id'];sha=candidates[0]['appProperties']['health_archive_sha256']
        else:
            if mode=='activate':raise SourceStop('activation_requires_prior_candidate_and_full_recovery')
            capture_root=root/'capture';capture_root.mkdir(mode=0o700)
            package=preview(capture_root,config)
            if package.get('restricted_capture_role_enforced') is not True:raise SourceStop('restricted_capture_required_for_pipeline')
            target=cloud.upload(capture_root/'package/complete-recovery.zip',package,producer_sha);sha=package['archive_sha256']
        if mode=='activate' and sha!=os.environ.get('HEALTH_RELEASE_CANDIDATE_SHA256'):
            raise SourceStop('release_candidate_digest_does_not_match_approved_archive')
        # Never adopt a candidate uploaded by the old SHEDULLER or another SHA.
        selected=cloud.meta(target).get('appProperties',{})
        require_candidate_binding(selected,producer_sha,sha)
        archive=cloud.download(target,sha,'remote-roundtrip')
        recovery_root=root/'remote-recovery';recovery_root.mkdir(mode=0o700)
        recovery_config=os.environ.get('HEALTH_COMPLETE_RECOVERY_RCLONE') if mode in ('candidate','activate') else None
        if mode in ('candidate','activate') and not recovery_config:raise SourceStop('primary_writer_and_independent_reader_recovery_config_required')
        proof=recover_archive(archive,sha,recovery_root,recovery_config)
        if proof['source_archive'].get('restricted_capture_role_enforced') is not True or proof['source_archive'].get('capture_role')!='health_backup_reader':raise SourceStop('remote_archive_restricted_capture_required')
        if executor_binding()!=(executor_sha,pins):raise SourceStop('pipeline_executor_changed_during_run')
        aggregate={'status':'ACTUAL_REMOTE_COMPLETE_CANDIDATE_RECOVERY_PASS','producer_sha':producer_sha,'executor_sha':executor_sha,'candidate_file_sha256':pins,'candidate_folder_id':target,'archive_sha256':sha,'archive_bytes':archive.stat().st_size,'remote_roundtrip_verified':True,'recovery':proof,'capacity_policy':'OWNER_ASSUMED_FUTURE_CAPACITY_20261012','quota_checked':False,'daily_backup_activated':False,'production_cutover':False,'permanent_deletes':0}
        if mode!='candidate':
            # The callback proof was freshly generated locally from this exact
            # remote ZIP. It is never taken from an uploaded acceptance receipt.
            if executor_binding()!=(executor_sha,pins):raise SourceStop('rotation_executor_changed')
            rotation=DriveRotation(cloud.t,cloud.parent,journal,verification='daily' if mode=='daily' else 'full',executor_sha=executor_sha)
            aggregate['rotation']=rotation.promote(target,sha,lambda id:proof if id==target else {})
            if mode=='activate':
                props={'health_backup_pipeline':'v1','health_recovery_executor':executor_sha,'health_full_restore_archive':sha}
                cloud.t.request('/drive/v3/files/'+cloud.parent+'?fields=id,appProperties',method='PATCH',body=json.dumps({'appProperties':props}).encode(),content_type='application/json')
                readback=cloud.meta(cloud.parent).get('appProperties',{})
                if any(readback.get(k)!=v for k,v in props.items()):raise SourceStop('full_activation_marker_readback_failed')
                # One-time bootstrap retirement was completed and read back in
                # authenticated activation 38263084066 (2026-10-12). Repeating
                # that lookup would make every future activation depend on a
                # historic trash object, which Drive eventually removes.
                # Ongoing rotation only retires the exact previous ACTIVE set.
                aggregate['bootstrap_retirement']='COMPLETED_PRIOR_ACTIVATION_38263084066_NOT_REPEATED'
            aggregate.update(status='ACTUAL_VERIFIED_COMPLETE_BACKUP_ROTATION_PASS',complete_set_promoted=True,daily_backup_activated=mode=='daily',verification_mode=mode)
        (root/'pipeline-aggregate.json').write_text(json.dumps(aggregate,indent=2));return aggregate
    finally:
        if journal:journal.close()
        cloud.close()

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--mode',choices=['candidate','activate','daily'],required=True);args=parser.parse_args()
    try:
        if os.environ.get('GITHUB_REPOSITORY')!='Alexio00/HEALTH' or os.environ.get('GITHUB_REF')!='refs/heads/main' or os.environ.get('HEALTH_COMPLETE_SERIALIZED')!='1':raise SourceStop('exact_scheduler_workflow_identity_required')
        event=os.environ.get('GITHUB_EVENT_NAME','')
        if event not in ('schedule','workflow_dispatch'):raise SourceStop('scheduled_or_owner_dispatch_required')
        if event=='workflow_dispatch' and os.environ.get('GITHUB_ACTOR_ID')!='308028794':raise SourceStop('owner_dispatch_required')
        if args.mode!='daily' and event!='workflow_dispatch':raise SourceStop('activation_requires_owner_dispatch')
        producer=os.environ.get('HEALTH_BACKUP_PRODUCER_SHA','')
        if not re.fullmatch('[a-f0-9]{40}',producer):
            raise SourceStop('accepted_immutable_backup_producer_required')
        result=run(args.mode,Path(os.environ['HEALTH_COMPLETE_PRIVATE_ROOT']),producer,serialized=True)
        print(json.dumps({'status': result.get('status'), 'candidate_archive_sha256': result.get('archive_sha256') if args.mode=='candidate' else None, 'daily_backup_activated': result.get('daily_backup_activated', False), 'production_cutover': False, 'permanent_deletes': 0}))
    except (SourceStop,RotationStop,CutoverStop) as e:print(json.dumps({'status':'STOPPED','safe_reason':str(e),'permanent_deletes':0}));raise SystemExit(2)
    except Exception:print(json.dumps({'status':'STOPPED','safe_reason':'private_complete_pipeline_failed','permanent_deletes':0}));raise SystemExit(2)
