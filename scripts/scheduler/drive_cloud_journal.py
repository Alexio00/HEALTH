"""Private Drive checkpoint survives an ephemeral runner disappearing.

One old ACTIVE set is supported. The caller MUST serialize every rotation in
the same GitHub concurrency group. Drive metadata PATCH is not a CAS lock.
The local lock only protects processes on the same worker. Remote metadata is
untrusted state: it never substitutes for fresh archive/recovery verification.
"""
import json,re
from drive_rotation import OWNER,RotationJournal,RotationStop,identity

KEYS=('v','target','sha','old','old_sha','state','done')
PREFIX='health_r_'
class DriveCloudJournal:
    def __init__(self,transport,parent,local_lock_file,*,serialized):
        if serialized is not True:raise RotationStop('serialized_cloud_rotation_required')
        self.t=transport;self.parent=identity(parent)
        self.local=RotationJournal(local_lock_file)
    def close(self):self.local.close()
    def lock(self):return self.local.lock()
    def read(self):
        m=self.t.request('/drive/v3/files/'+self.parent+'?fields=id,mimeType,trashed,owners(emailAddress),permissions(type,role,emailAddress),appProperties')
        acl=m.get('permissions',[])
        if m.get('id')!=self.parent or m.get('mimeType')!='application/vnd.google-apps.folder' or m.get('trashed') is not False or m.get('owners')!=[{'emailAddress':OWNER}] or len(acl)!=1 or (acl[0].get('type'),acl[0].get('role'),acl[0].get('emailAddress'))!=('user','owner',OWNER):
            raise RotationStop('cloud_journal_private_parent_rejected')
        properties=m.get('appProperties',{})
        if not isinstance(properties,dict):raise RotationStop('cloud_journal_properties_rejected')
        p={k[len(PREFIX):]:v for k,v in properties.items() if k.startswith(PREFIX)}
        if not p:return None
        if set(p)!=set(KEYS) or any(not isinstance(v,str) for v in p.values()) or p['v']!='1':raise RotationStop('cloud_journal_format_rejected')
        if not re.fullmatch('[a-f0-9]{64}',p['sha']) or p['state'] not in ('PLANNED','PROMOTED','DONE') or p['done'] not in ('0','1'):
            raise RotationStop('cloud_journal_binding_rejected')
        target=identity(p['target']);old=[];done=[]
        if p['old']:
            old_id=identity(p['old'])
            if old_id==target or not re.fullmatch('[a-f0-9]{64}',p['old_sha']):raise RotationStop('cloud_journal_old_binding_rejected')
            old=[{'id':old_id,'sha':p['old_sha']}]
            if p['done']=='1':done=[old_id]
        elif p['old_sha'] or p['done']!='0':raise RotationStop('cloud_journal_empty_old_rejected')
        if p['state']=='PLANNED' and done or p['state']=='DONE' and len(old)!=len(done):raise RotationStop('cloud_journal_progress_rejected')
        return {'target':target,'parent':self.parent,'sha':p['sha'],'old':json.dumps(old),'done':json.dumps(done),'state':p['state']}
    def get(self,target):
        row=self.read()
        return row if row and row['target']==target else None
    def save(self,previous,row):
        if self.read()!=previous:raise RotationStop('cloud_journal_concurrent_change')
        old=json.loads(row['old']);done=json.loads(row['done'])
        if len(old)>1 or done not in ([],[old[0]['id']] if old else []):raise RotationStop('cloud_journal_single_old_required')
        p=dict(v='1',target=row['target'],sha=row['sha'],old=old[0]['id'] if old else '',
               old_sha=old[0]['sha'] if old else '',state=row['state'],done='1' if done else '0')
        properties={PREFIX+k:v for k,v in p.items()}
        if any(len(k.encode())+len(v.encode())>124 for k,v in properties.items()):raise RotationStop('cloud_journal_property_limit')
        self.t.request('/drive/v3/files/'+self.parent+'?fields=id,appProperties',method='PATCH',body=json.dumps({'appProperties':properties}).encode(),content_type='application/json')
        if self.read()!=row:raise RotationStop('cloud_journal_save_readback_failed')
    def plan(self,target,parent,sha,old):
        target=identity(target)
        if parent!=self.parent or not re.fullmatch('[a-f0-9]{64}',sha):raise RotationStop('cloud_journal_plan_binding_rejected')
        previous=self.read()
        if previous and previous['target']==target:
            if previous['sha']!=sha:raise RotationStop('rotation_replay_binding_changed')
            return previous
        if previous and previous['state']!='DONE':raise RotationStop('previous_rotation_needs_reconciliation')
        if len(old)>1:raise RotationStop('cloud_journal_single_old_required')
        for binding in old:
            identity(binding['id'])
            if binding['id']==target or not re.fullmatch('[a-f0-9]{64}',binding['sha']):raise RotationStop('cloud_journal_old_binding_rejected')
        row=dict(target=target,parent=parent,sha=sha,old=json.dumps(old),done='[]',state='PLANNED')
        self.save(previous,row);return row
    def state(self,target,state,done=None):
        row=self.get(target)
        if row is None or state not in ('PROMOTED','DONE') or row['state']=='DONE' and state!='DONE':raise RotationStop('cloud_journal_transition_rejected')
        updated=dict(row,state=state)
        if done is not None:updated['done']=json.dumps(done)
        if state=='DONE' and len(json.loads(updated['old']))!=len(json.loads(updated['done'])):raise RotationStop('cloud_journal_done_before_trash_rejected')
        self.save(row,updated)
