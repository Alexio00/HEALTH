"""One complete recovery set: verify new, promote, then trash exact old IDs.

The caller supplies a trusted restore executor, a private persistent journal,
and serializes all cloud writers (the daily workflow concurrency boundary).
An uploaded receipt alone is not an authorized restore executor. No DELETE API.
"""
from contextlib import contextmanager
import json,os,re,sqlite3,urllib.parse
from pathlib import Path

HEALTH_PARENT=os.environ.get('HEALTH_BACKUP_PARENT_FOLDER_ID', '')
OWNER=os.environ.get('HEALTH_BACKUP_DRIVE_OWNER_EMAIL', '')
class RotationStop(RuntimeError):pass
def identity(value):
    if not isinstance(value,str) or not re.fullmatch('[A-Za-z0-9_-]{8,128}',value):raise RotationStop('rotation_identity_rejected')
    return value

class RotationJournal:
    def __init__(self,path):
        self.path=Path(path)
        if self.path.is_symlink() or self.path.parent.is_symlink() or not self.path.parent.is_dir():raise RotationStop('private_rotation_journal_required')
        if os.name!='nt' and self.path.parent.stat().st_mode&0o077:raise RotationStop('private_rotation_journal_required')
        if not self.path.exists():fd=os.open(self.path,os.O_CREAT|os.O_EXCL|os.O_RDWR,0o600);os.close(fd)
        self.db=sqlite3.connect(self.path);self.db.row_factory=sqlite3.Row
        self.db.execute('PRAGMA journal_mode=WAL');self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('CREATE TABLE IF NOT EXISTS rotations(target TEXT PRIMARY KEY,parent TEXT NOT NULL,sha TEXT NOT NULL,old TEXT NOT NULL,done TEXT NOT NULL,state TEXT NOT NULL)');self.db.commit()
    def close(self):self.db.close()
    @contextmanager
    def lock(self):
        path=self.path.parent/'rotation.lock'
        if path.is_symlink():raise RotationStop('rotation_lock_path_rejected')
        file=os.fdopen(os.open(path,os.O_CREAT|os.O_RDWR,0o600),'r+b',buffering=0)
        try:
            if os.fstat(file.fileno()).st_size==0:file.write(b'\0');file.seek(0)
            try:
                if os.name=='nt':
                    import msvcrt;msvcrt.locking(file.fileno(),msvcrt.LK_NBLCK,1)
                else:
                    import fcntl;fcntl.flock(file.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
            except OSError:raise RotationStop('rotation_concurrently_locked') from None
            yield
        finally:file.close()
    def get(self,target):
        row=self.db.execute('SELECT * FROM rotations WHERE target=?',(target,)).fetchone()
        return dict(row) if row else None
    def plan(self,target,parent,sha,old):
        for binding in old:
            if (not isinstance(binding,dict) or set(binding)!={'id','sha','zip_id'}
                    or identity(binding['id'])==identity(binding['zip_id'])
                    or not isinstance(binding['sha'],str)
                    or not re.fullmatch('[a-f0-9]{64}',binding['sha'])):
                raise RotationStop('rotation_old_zip_id_binding_required')
        row=self.get(target)
        if row:
            if (row['parent'],row['sha'])!=(parent,sha):raise RotationStop('rotation_replay_binding_changed')
            return row
        if self.db.execute("SELECT count(*) FROM rotations WHERE state!='DONE'").fetchone()[0]:raise RotationStop('previous_rotation_needs_reconciliation')
        with self.db:self.db.execute("INSERT INTO rotations VALUES(?,?,?,?,?,'PLANNED')",(target,parent,sha,json.dumps(old),'[]'))
        return self.get(target)
    def state(self,target,state,done=None):
        with self.db:
            if done is None:self.db.execute('UPDATE rotations SET state=? WHERE target=?',(state,target))
            else:self.db.execute('UPDATE rotations SET state=?,done=? WHERE target=?',(state,json.dumps(done),target))

class DriveRotation:
    def __init__(self,transport,parent,journal,test=False,verification='full',executor_sha=None):
        self.t=transport;self.parent=identity(parent);self.j=journal;self.test=test
        if verification not in ('full','daily'):raise RotationStop('rotation_verification_mode_rejected')
        self.verification=verification
        if self.t.request('/drive/v3/about?fields=user(emailAddress)')['user']['emailAddress']!=OWNER:raise RotationStop('backup_account_identity_rejected')
        meta=self.meta(self.parent)
        if verification=='daily' and not test:
            p=meta.get('appProperties',{})
            if not isinstance(executor_sha,str) or not re.fullmatch('[a-f0-9]{64}',executor_sha) or p.get('health_backup_pipeline')!='v1' or p.get('health_recovery_executor')!=executor_sha or not re.fullmatch('[a-f0-9]{64}',p.get('health_full_restore_archive','')):
                raise RotationStop('same_executor_full_activation_restore_required')
        if meta.get('mimeType')!='application/vnd.google-apps.folder' or meta.get('trashed') is not False:raise RotationStop('complete_set_parent_rejected')
        if test:
            if not re.fullmatch('HEALTH_SYNTHETIC_BACKUP_ROTATION_[A-Za-z0-9_-]+',meta.get('name','')):raise RotationStop('disposable_rotation_parent_required')
        elif meta.get('name')!='CompleteSets' or meta.get('parents')!=[HEALTH_PARENT]:raise RotationStop('complete_set_parent_rejected')
    def meta(self,id):
        m=self.t.request('/drive/v3/files/'+identity(id)+'?fields=id,name,parents,mimeType,trashed,appProperties,size,sha256Checksum,owners(emailAddress),permissions(type,role,emailAddress)')
        permissions=m.get('permissions')
        if m.get('owners')!=[{'emailAddress':OWNER}] or not isinstance(permissions,list) or len(permissions)!=1 or permissions[0].get('type')!='user' or permissions[0].get('role')!='owner' or permissions[0].get('emailAddress')!=OWNER:raise RotationStop('private_backup_owner_acl_required')
        return m
    def children(self,parent,include_trashed=False):
        # A retired folder is itself in Trash. An inventory filtered by
        # `trashed=false` cannot prove the identity of its physical ZIP.
        query="'"+identity(parent)+"' in parents"
        if not include_trashed:query+=' and trashed=false'
        q=urllib.parse.urlencode({'q':query,'fields':'files(id),nextPageToken','pageSize':1000})
        result=self.t.request('/drive/v3/files?'+q)
        if result.get('nextPageToken') or not isinstance(result.get('files'),list):
            raise RotationStop('rotation_inventory_incomplete')
        return [self.meta(x['id']) for x in result['files']]
    def set(self,id,expected_sha=None,allow_trashed=False,expected_zip_id=None,with_archive=False):
        meta=self.meta(id);p=meta.get('appProperties',{})
        if meta.get('parents')!=[self.parent] or meta.get('mimeType')!='application/vnd.google-apps.folder' or (meta.get('trashed') is not False and not allow_trashed) or p.get('health_complete_set')!='v1' or not re.fullmatch('complete-[0-9]{8}T[0-9]{6}Z-[a-f0-9]{8}',meta.get('name','')):raise RotationStop('managed_complete_set_identity_rejected')
        sha=p.get('health_archive_sha256','')
        if not re.fullmatch('[a-f0-9]{64}',sha) or expected_sha is not None and expected_sha!=sha:raise RotationStop('complete_set_digest_binding_rejected')
        # Also inspect the physical ZIP inside a trashed retired set. The
        # journal binds the folder SHA, while Drive independently reports the
        # stored binary's SHA-256 and size. Missing metadata is never PASS.
        files=self.children(id,include_trashed=allow_trashed)
        size=p.get('health_archive_bytes')
        if (not isinstance(size,str) or not re.fullmatch('[1-9][0-9]*',size)):
            raise RotationStop('complete_set_archive_size_binding_rejected')
        if len(files)!=1:
            raise RotationStop('complete_set_physical_archive_identity_rejected')
        archive=files[0]
        if (not isinstance(archive.get('id'),str) or
                not re.fullmatch('[A-Za-z0-9_-]{8,128}',archive['id']) or
                archive.get('parents')!=[id] or
                archive.get('name')!='complete-recovery.zip' or
                archive.get('mimeType')!='application/zip'):
            raise RotationStop('complete_set_physical_archive_identity_rejected')
        if expected_zip_id is not None and archive['id']!=identity(expected_zip_id):
            raise RotationStop('complete_set_physical_archive_id_binding_rejected')
        if archive.get('sha256Checksum')!=sha:
            raise RotationStop('complete_set_physical_archive_checksum_rejected')
        if str(archive.get('size',''))!=size:
            raise RotationStop('complete_set_physical_archive_size_rejected')
        return (meta,archive) if with_archive else meta
    def retired_binding(self,id):
        folder,archive=self.set(id,with_archive=True)
        return {'id':id,'sha':folder['appProperties']['health_archive_sha256'],
                'zip_id':archive['id']}
    def patch(self,id,payload):return self.t.request('/drive/v3/files/'+identity(id)+'?fields=id,trashed,appProperties',method='PATCH',body=json.dumps(payload).encode(),content_type='application/json')
    def verify_retired(self,binding):
        # A recorded Trash acknowledgement is not proof that the old folder
        # still matches the immutable journal binding on a later retry.
        previous=self.set(binding['id'],binding['sha'],allow_trashed=True,
                          expected_zip_id=identity(binding['zip_id']))
        if previous['appProperties'].get('health_recovery_state')!='ACTIVE':
            raise RotationStop('completed_rotation_old_state_changed')
        if previous.get('trashed') is not True:
            raise RotationStop('completed_rotation_old_not_trashed')

    def verify_mutation_preflight(self,target,sha,old,done):
        current=self.set(target,sha)
        target_state=current['appProperties'].get('health_recovery_state')
        if target_state not in ('CANDIDATE','ACTIVE'):raise RotationStop('rotation_target_state_changed')
        expected=set()
        for binding in old:
            previous=self.set(binding['id'],binding['sha'],allow_trashed=True,
                              expected_zip_id=identity(binding['zip_id']))
            if previous['appProperties'].get('health_recovery_state')!='ACTIVE':raise RotationStop('previous_active_set_changed')
            if binding['id'] in done and previous.get('trashed') is not True:raise RotationStop('completed_rotation_old_not_trashed')
            if previous.get('trashed') is False:expected.add(binding['id'])
        if target_state=='ACTIVE':expected.add(target)
        actual=[m['id'] for m in self.children(self.parent)
                if m.get('appProperties',{}).get('health_complete_set')=='v1'
                and m.get('appProperties',{}).get('health_recovery_state')=='ACTIVE']
        if len(actual)!=len(set(actual)) or set(actual)!=expected:raise RotationStop('rotation_active_inventory_changed')
        return target_state

    def promote(self,target,sha,restore):
        target=identity(target)
        with self.j.lock():
            new=self.set(target,sha)
            state=new['appProperties'].get('health_recovery_state')
            row=self.j.get(target)
            if row is None and state!='CANDIDATE':raise RotationStop('new_candidate_or_recovery_journal_required')
            if state not in ('CANDIDATE','ACTIVE'):raise RotationStop('candidate_state_rejected')
            active=[m['id'] for m in self.children(self.parent) if m['id']!=target and m.get('appProperties',{}).get('health_complete_set')=='v1' and m.get('appProperties',{}).get('health_recovery_state')=='ACTIVE']
            if row is None and len(active)>1:raise RotationStop('ambiguous_active_complete_sets')
            bindings=[self.retired_binding(id) for id in active] if row is None else []
            row=self.j.plan(target,self.parent,sha,bindings)
            old=json.loads(row['old']);done=json.loads(row['done'])
            # A legacy journal cannot establish original ZIP identity after Trash.
            # Never synthesize a missing binding from current Drive state.
            for binding in old:
                if (not isinstance(binding,dict) or set(binding)!={'id','sha','zip_id'}
                        or identity(binding['id'])==identity(binding['zip_id'])
                        or not isinstance(binding['sha'],str)
                        or not re.fullmatch('[a-f0-9]{64}',binding['sha'])):
                    raise RotationStop('rotation_old_zip_id_binding_required')
            if len(done)!=len(set(done)) or set(done)-{b['id'] for b in old}:
                raise RotationStop('rotation_done_binding_invalid')
            if set(active)-{b['id'] for b in old}:raise RotationStop('concurrent_active_set_change')
            # Always re-read the complete new archive through the trusted executor,
            # including retry after a lost provider reply. Never inherit old PASS.
            proof=restore(target)
            wanted='ACTUAL_SYNTHETIC_SET_BYTES_READBACK_PASS' if self.test else ('ACTUAL_COMPLETE_SET_RESTORE_PASS' if self.verification=='full' else 'ACTUAL_COMPLETE_ARCHIVE_DATABASE_AUTH_RESTORE_PASS')
            if proof.get('status')!=wanted or proof.get('archive_sha256')!=sha:raise RotationStop('complete_new_restore_not_accepted')
            required=('all_members_verified','database_restore_pass','auth_http_pass','source_rebind_pass') if self.verification=='full' else ('all_members_verified','database_restore_pass','auth_http_pass','source_corpus_bytes_verified','source_graph_binding_verified')
            if not self.test and not all(proof.get(k) is True for k in required):raise RotationStop('complete_new_restore_scope_incomplete')
            self.set(target,sha)
            if row['state']=='DONE':
                # Remote DONE may have committed even if the runner lost the
                # response. Never downgrade it or issue another PATCH/Trash.
                if state!='ACTIVE' or len(old)!=len(done) or set(done)!={x['id'] for x in old}:
                    raise RotationStop('completed_rotation_binding_rejected')
                for binding in old:
                    self.verify_retired(binding)
            else:
                if row['state']=='PROMOTED':
                    if state!='ACTIVE':raise RotationStop('promoted_rotation_target_not_active')
                    # Already recorded done entries must be reverified before
                    # any journal PATCH or further Trash mutation.
                    for binding in old:
                        if binding['id'] in done:self.verify_retired(binding)
                self.verify_mutation_preflight(target,sha,old,done)
                if state=='CANDIDATE':
                    self.patch(target,{'appProperties':{'health_recovery_state':'ACTIVE'}})
                if self.set(target,sha)['appProperties'].get('health_recovery_state')!='ACTIVE':raise RotationStop('new_active_readback_failed')
                self.verify_mutation_preflight(target,sha,old,done)
                self.j.state(target,'PROMOTED',done)
                for binding in old:
                    id=binding['id']
                    if id in done:continue
                    # Re-read every binding and the ACTIVE inventory before Trash.
                    self.verify_mutation_preflight(target,sha,old,done)
                    previous=self.set(id,binding['sha'],allow_trashed=True,
                                      expected_zip_id=identity(binding['zip_id']))
                    if previous['appProperties'].get('health_recovery_state')!='ACTIVE':raise RotationStop('previous_active_set_changed')
                    if previous.get('trashed') is not True:self.patch(id,{'trashed':True})
                    if self.set(id,binding['sha'],allow_trashed=True,
                                expected_zip_id=identity(binding['zip_id'])).get('trashed') is not True:
                        raise RotationStop('previous_set_trash_readback_failed')
                    done.append(id)
                    self.verify_mutation_preflight(target,sha,old,done)
                    self.j.state(target,'PROMOTED',done)
                self.verify_mutation_preflight(target,sha,old,done)
                self.j.state(target,'DONE',done)
            if [m['id'] for m in self.children(self.parent) if m.get('appProperties',{}).get('health_complete_set')=='v1' and m.get('appProperties',{}).get('health_recovery_state')=='ACTIVE']!=[target]:raise RotationStop('one_active_set_readback_failed')
            return {'status':'ONE_VERIFIED_ACTIVE_COMPLETE_SET_ROTATION_PASS','previous_sets_trashed':len(done),'permanent_deletes':0,'test_only':self.test}
