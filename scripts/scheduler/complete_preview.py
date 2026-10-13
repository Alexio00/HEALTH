"""Portable private capture/package preview; no Drive writes or activation.

The lineage seed is the previously uploaded owner-private candidate, bound to
exact Drive IDs and ZIP SHA. It supplies frozen lineage metadata only. No old
restore PASS is inherited by the new candidate.
"""
import configparser, json, os, re, subprocess, urllib.request, zipfile
from complete_coordination import capture_lock
from pathlib import Path
from complete_archive import digest, verify_archive
from complete_sources import NoRedirect, SourceStop, capture_sources, package_candidate, private, FROZEN_SHA

SEED_FOLDER=os.environ.get('HEALTH_HISTORICAL_SEED_FOLDER_ID', '')
SEED_FILE=os.environ.get('HEALTH_HISTORICAL_SEED_FILE_ID', '')
SEED_SHA=os.environ.get('HEALTH_HISTORICAL_SEED_SHA256', '')

def lineage_seed(config,output):
    cfg=configparser.ConfigParser(interpolation=None);cfg.read(config,encoding='utf-8')
    if cfg['health_backup'].get('type')!='drive' or cfg['health_backup'].get('scope')!='drive':
        raise SourceStop('backup_owner_config_required')
    # After activation, lineage comes from the current ACTIVE complete archive.
    # Its entire ZIP is freshly verified; no historical restore PASS is reused.
    from complete_cloud import CompleteCloud
    cloud_root=output/'cloud-metadata';cloud_root.mkdir(mode=0o700)
    cloud=CompleteCloud(Path(config).read_text(encoding='utf-8'),cloud_root)
    seed_folder,seed_file,seed_sha=SEED_FOLDER,SEED_FILE,SEED_SHA
    try:
        active=[x for x in cloud.children(cloud.parent) if x.get('appProperties',{}).get('health_complete_set')=='v1' and x.get('appProperties',{}).get('health_recovery_state')=='ACTIVE']
        if len(active)>1:raise SourceStop('lineage_active_archive_ambiguous')
        if active:
            seed_folder=active[0]['id'];seed_sha=active[0]['appProperties'].get('health_archive_sha256','')
            if not re.fullmatch('[a-f0-9]{64}',seed_sha):raise SourceStop('lineage_active_digest_rejected')
            files=cloud.children(seed_folder)
            if len(files)!=1 or files[0].get('name')!='complete-recovery.zip' or files[0].get('sha256Checksum')!=seed_sha:raise SourceStop('lineage_active_archive_rejected')
            seed_file=files[0]['id']
    finally:cloud.close()
    if not all((seed_folder,seed_file,seed_sha)):
        raise SourceStop('lineage_seed_missing_after_active_lookup')
    scoped=configparser.ConfigParser(interpolation=None)
    scoped['complete_seed_reader']=dict(cfg['health_backup']);scoped['complete_seed_reader']['root_folder_id']=seed_folder
    file=output/'seed.private.conf'
    with file.open('x',encoding='utf-8') as f:scoped.write(f)
    file.chmod(0o600)
    def clone(command,*args):
        p=subprocess.run(['rclone',command,*map(str,args),'--config',str(file),'--log-file',str(output/'seed.private.log'),'--log-level','ERROR'],capture_output=True,timeout=1800)
        if p.returncode:raise SourceStop('lineage_seed_read_failed_'+command)
        return p.stdout
    def get(path):
        current=configparser.ConfigParser(interpolation=None);current.read(file,encoding='utf-8')
        token=json.loads(current['complete_seed_reader']['token'])['access_token']
        req=urllib.request.Request('https://www.googleapis.com'+path,headers={'Authorization':'Bearer '+token})
        try:
            with urllib.request.build_opener(NoRedirect()).open(req,timeout=30) as r:return json.loads(r.read(1048576))
        except Exception:raise SourceStop('lineage_seed_metadata_failed') from None
    try:
        clone('lsf','complete_seed_reader:','--max-depth','1','--dirs-only')
        if get('/drive/v3/about?fields=user(emailAddress)')['user']['emailAddress']!=os.environ.get('HEALTH_BACKUP_DRIVE_OWNER_EMAIL', ''):
            raise SourceStop('lineage_seed_owner_identity_rejected')
        fields='id,name,parents,trashed,mimeType,sha256Checksum,owners(emailAddress),permissions(type,role,emailAddress)'
        for id in (seed_folder,seed_file):
            meta=get('/drive/v3/files/'+id+'?fields='+fields);acl=meta.get('permissions',[])
            if meta.get('id')!=id or meta.get('trashed') is not False or meta.get('owners')!=[{'emailAddress':os.environ.get('HEALTH_BACKUP_DRIVE_OWNER_EMAIL', '')}] or len(acl)!=1 or (acl[0].get('type'),acl[0].get('role'),acl[0].get('emailAddress'))!=('user','owner',os.environ.get('HEALTH_BACKUP_DRIVE_OWNER_EMAIL', '')):
                raise SourceStop('lineage_seed_private_binding_rejected')
            if id==seed_file and (meta.get('parents')!=[seed_folder] or meta.get('name')!='complete-recovery.zip' or meta.get('sha256Checksum')!=seed_sha):
                raise SourceStop('lineage_seed_archive_binding_rejected')
        inventory=json.loads(clone('lsjson','complete_seed_reader:'))
        matching=[x for x in inventory if x.get('Name')=='complete-recovery.zip' and not x.get('IsDir')]
        if len(matching)!=1 or matching[0].get('ID')!=seed_file:raise SourceStop('lineage_seed_archive_not_unique')
        archive=output/'seed.private.zip';clone('copyto','complete_seed_reader:complete-recovery.zip',archive,'--immutable')
        verify_archive(archive,seed_sha)
        frozen=output/'frozen-original-inventory.private.json'
        with zipfile.ZipFile(archive) as z:frozen.write_bytes(z.read('metadata/frozen-original-inventory.private.json'))
        if digest(frozen)!=FROZEN_SHA:raise SourceStop('frozen_original_inventory_pin_mismatch')
        return frozen
    finally:file.unlink()

def preview(root,config_content):
    root=private(root,fresh=True)
    config=root/'rclone.private.conf';config.write_text(config_content,encoding='utf-8');config.chmod(0o600)
    dbroot=root/'database-capture';dbroot.mkdir(mode=0o700)
    env=os.environ.copy();env['HEALTH_COMPLETE_PRIVATE_ROOT']=str(dbroot)
    try:
        coordinator=capture_lock(root)
        with coordinator:
            return _coordinated_preview(root,config,env,dbroot,coordinator)
    finally:config.unlink()

def _coordinated_preview(root,config,env,dbroot,coordinator):
    try:
        with (root/'capture.private.stdout').open('wb') as out,(root/'capture.private.stderr').open('wb') as err:
            p=subprocess.run(['python3' if os.name!='nt' else 'python',str(Path(__file__).with_name('complete_capture.py'))],env=env,stdout=out,stderr=err,timeout=1800)
        if p.returncode:raise SourceStop('portable_database_capture_failed')
        coordinator.assert_held()
        locator=json.loads((dbroot/'capture-locator.private.json').read_text());database=Path(locator['private_folder'])
        if not database.resolve().is_relative_to(dbroot.resolve()):raise SourceStop('private_capture_locator_rejected')
        capture=json.loads((database/'capture.private.json').read_text())
        sources=root/'source-capture';sources.mkdir(mode=0o700)
        source_proof=capture_sources(database,config,sources)
        coordinator.assert_held()
        seed=root/'lineage-seed';seed.mkdir(mode=0o700);frozen=lineage_seed(config,seed)
        package=root/'package';package.mkdir(mode=0o700)
        proof=package_candidate(database,sources,frozen,package)
        coordinator.assert_held()
        if os.environ.get('HEALTH_PREVIEW_RESTORE_DATABASE_AUTH')=='1':
            from complete_recovery import recover_archive
            recovery=root/'recovery';recovery.mkdir(mode=0o700)
            proof['fresh_database_auth_restore']=recover_archive(package/'complete-recovery.zip',proof['archive_sha256'],recovery)
        proof.update(status='ACTUAL_PORTABLE_COMPLETE_PREVIEW_PACKAGE_PASS',source_capture=source_proof,
            workflow_sha=os.environ.get('GITHUB_SHA'),run_id=os.environ.get('GITHUB_RUN_ID'),run_attempt=os.environ.get('GITHUB_RUN_ATTEMPT'),
            restricted_capture_role_enforced=capture['restricted_role_enforced'],capture_role=capture['capture_role'],full_replacement_backup_accepted=False,
            source_writer_serialization_enforced=True,coordination_key=63741020261013,production_activation=False)
        (root/'preview-aggregate.json').write_text(json.dumps(proof,indent=2))
        return proof
    finally:pass

if __name__=='__main__':
    try:print(json.dumps(preview(os.environ['HEALTH_COMPLETE_PRIVATE_ROOT'],os.environ['RCLONE_CONFIG_CONTENT'])))
    except SourceStop as e:print(json.dumps({'status':'STOPPED','safe_reason':str(e),'production_writes':False}));raise SystemExit(2)
    except Exception:print(json.dumps({'status':'STOPPED','safe_reason':'private_complete_preview_failed','production_writes':False}));raise SystemExit(2)
