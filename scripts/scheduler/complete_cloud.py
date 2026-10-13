"""Owner-private candidate upload and fresh remote ZIP readback. No rotation."""
import configparser,json,re,subprocess,urllib.parse
from pathlib import Path
from complete_archive import digest
from complete_sources import private,SourceStop
from drive_transport import DriveTransport
from drive_rotation import OWNER,HEALTH_PARENT,identity,RotationStop

FIELDS='id,name,parents,mimeType,trashed,appProperties,size,sha256Checksum,owners(emailAddress),permissions(type,role,emailAddress)'
class CompleteCloud:
    def __init__(self,config_content,root):
        self.root=private(root,fresh=True);self.config=self.root/'backup.private.conf'
        self.config.write_text(config_content,encoding='utf-8');self.config.chmod(0o600)
        c=self.config_data()
        if c['health_backup'].get('type')!='drive' or c['health_backup'].get('scope')!='drive':raise SourceStop('backup_owner_configuration_required')
        self.clone('lsf','health_backup:','--max-depth','1','--dirs-only')
        self.t=DriveTransport(self.token)
        if self.t.request('/drive/v3/about?fields=user(emailAddress)')['user']['emailAddress']!=OWNER:raise SourceStop('backup_owner_identity_rejected')
        health=self.meta(HEALTH_PARENT)
        if health.get('name')!='HEALTH' or health.get('mimeType')!='application/vnd.google-apps.folder':raise SourceStop('backup_health_root_rejected')
        query=urllib.parse.urlencode({'q':"'"+HEALTH_PARENT+"' in parents and trashed=false and name='CompleteSets'",'fields':'files(id),nextPageToken','pageSize':1000})
        found=self.t.request('/drive/v3/files?'+query)
        if found.get('nextPageToken'):raise SourceStop('complete_sets_lookup_overflow')
        folders=[self.meta(x['id']) for x in found.get('files',[])]
        if len(folders)!=1 or folders[0].get('mimeType')!='application/vnd.google-apps.folder':raise SourceStop('unique_complete_sets_parent_required')
        self.parent=folders[0]['id']
    def config_data(self):
        c=configparser.ConfigParser(interpolation=None);c.read(self.config,encoding='utf-8');return c
    def token(self):return json.loads(self.config_data()['health_backup']['token'])['access_token']
    def clone(self,command,*args,config=None):
        p=subprocess.run(['rclone',command,*map(str,args),'--config',str(config or self.config),'--retries','1','--low-level-retries','1','--log-file',str(self.root/'cloud.private.log'),'--log-level','ERROR'],capture_output=True,timeout=1800)
        if p.returncode:raise SourceStop('complete_cloud_rclone_'+command+'_failed')
        return p.stdout
    def meta(self,id,allow_trashed=False):
        m=self.t.request('/drive/v3/files/'+identity(id)+'?fields='+FIELDS);acl=m.get('permissions',[])
        if m.get('id')!=id or m.get('trashed') is not False and not allow_trashed or m.get('owners')!=[{'emailAddress':OWNER}] or len(acl)!=1 or (acl[0].get('type'),acl[0].get('role'),acl[0].get('emailAddress'))!=('user','owner',OWNER):raise SourceStop('complete_cloud_owner_acl_rejected')
        return m
    def children(self,parent):
        query=urllib.parse.urlencode({'q':"'"+identity(parent)+"' in parents and trashed=false",'pageSize':1000,'fields':'files(id),nextPageToken'})
        data=self.t.request('/drive/v3/files?'+query)
        if data.get('nextPageToken'):raise SourceStop('complete_cloud_inventory_overflow')
        return [self.meta(x['id']) for x in data.get('files',[])]
    def scoped(self,parent,label):
        c=configparser.ConfigParser(interpolation=None);c['complete_candidate_owner']=dict(self.config_data()['health_backup'])
        c['complete_candidate_owner']['root_folder_id']=identity(parent)
        file=self.root/(label+'.private.conf')
        with file.open('x',encoding='utf-8') as f:c.write(f)
        file.chmod(0o600);return file
    def upload(self,archive,proof,producer_sha):
        archive=Path(archive);sha=proof['archive_sha256'];name=proof['candidate_id']
        if not re.fullmatch('[a-f0-9]{40}',producer_sha) or not re.fullmatch('complete-[0-9]{8}T[0-9]{6}Z-[a-f0-9]{8}',name) or digest(archive)!=sha or archive.stat().st_size!=proof['archive_bytes']:raise SourceStop('complete_cloud_input_binding_rejected')
        # Owner accepted future capacity on 2026-10-12; do not query quota.
        # Provider upload failure leaves the existing ACTIVE archive intact.
        if any(x.get('name')==name for x in self.children(self.parent)):raise SourceStop('candidate_name_already_exists_reconcile_required')
        properties={'health_complete_set':'v1','health_recovery_state':'UPLOADING','health_archive_sha256':sha,'health_archive_bytes':str(archive.stat().st_size),'health_pipeline_commit':producer_sha}
        request={'name':name,'mimeType':'application/vnd.google-apps.folder','parents':[self.parent],'appProperties':properties}
        (self.root/'upload-plan.private.json').write_text(json.dumps(request,indent=2))
        result=self.t.request('/drive/v3/files?fields=id',method='POST',body=json.dumps(request).encode(),content_type='application/json')
        folder=identity(result['id']);(self.root/'upload-folder.private.json').write_text(json.dumps({'folder':folder,'sha':sha}))
        meta=self.meta(folder)
        if meta.get('parents')!=[self.parent] or meta.get('appProperties')!=properties or meta.get('name')!=name:raise SourceStop('new_candidate_folder_readback_rejected')
        config=self.scoped(folder,'upload')
        try:self.clone('copyto',archive,'complete_candidate_owner:complete-recovery.zip','--immutable',config=config)
        finally:config.unlink()
        self.finish_upload(meta,producer_sha)
        return folder
    def finish_upload(self,folder_meta,producer_sha):
        """Promote only a fully downloaded ZIP; retry one exact orphan safely."""
        folder=identity(folder_meta.get('id'))
        m=self.meta(folder);p=m.get('appProperties',{});sha=p.get('health_archive_sha256','')
        if (m.get('parents')!=[self.parent] or m.get('trashed') is not False
                or m.get('mimeType')!='application/vnd.google-apps.folder'
                or not re.fullmatch('complete-[0-9]{8}T[0-9]{6}Z-[a-f0-9]{8}',m.get('name',''))
                or p.get('health_complete_set')!='v1'
                or p.get('health_pipeline_commit')!=producer_sha
                or not re.fullmatch('[a-f0-9]{64}',sha)
                or not p.get('health_archive_bytes','').isdigit()
                or int(p['health_archive_bytes'])<=0
                or p.get('health_recovery_state') not in ('UPLOADING','CANDIDATE')):
            raise SourceStop('orphan_upload_identity_requires_owner_reconciliation')
        # download verifies provider hash and size and local bytes; fail on partial ZIP.
        self.download(folder,sha,'upload-reconcile',allow_uploading=True)
        if p['health_recovery_state']=='UPLOADING':
            try:
                self.t.request('/drive/v3/files/'+folder+'?fields=id,appProperties',
                               method='PATCH',body=json.dumps({'appProperties':{'health_recovery_state':'CANDIDATE'}}).encode(),
                               content_type='application/json')
            except Exception:
                if self.meta(folder).get('appProperties',{}).get('health_recovery_state')!='CANDIDATE':
                    raise
        done=self.meta(folder).get('appProperties',{})
        if done.get('health_recovery_state')!='CANDIDATE' or done.get('health_pipeline_commit')!=producer_sha or done.get('health_archive_sha256')!=sha:
            raise SourceStop('upload_final_state_readback_rejected')
        return folder,sha
    def download(self,folder,expected_sha,label,*,allow_uploading=False):
        meta=self.meta(folder);p=meta.get('appProperties',{})
        if meta.get('parents')!=[self.parent] or p.get('health_complete_set')!='v1' or p.get('health_archive_sha256')!=expected_sha or p.get('health_recovery_state') not in (('UPLOADING','CANDIDATE','ACTIVE') if allow_uploading else ('CANDIDATE','ACTIVE')):raise SourceStop('candidate_remote_binding_rejected')
        files=self.children(folder)
        if len(files)!=1 or files[0].get('name')!='complete-recovery.zip' or files[0].get('sha256Checksum')!=expected_sha or int(files[0].get('size',0))!=int(p.get('health_archive_bytes',0)):raise SourceStop('candidate_remote_archive_rejected')
        target=self.root/(label+'.private.zip');config=self.scoped(folder,label)
        try:self.clone('copyto','complete_candidate_owner:complete-recovery.zip',target,'--immutable',config=config)
        finally:config.unlink()
        if digest(target)!=expected_sha or target.stat().st_size!=int(files[0]['size']):raise SourceStop('remote_candidate_roundtrip_changed')
        self.meta(folder);return target
    def close(self):
        if self.config.exists():self.config.unlink()
