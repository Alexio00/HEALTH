"""Rotation failures must preserve the old set and never DELETE or empty trash."""
import copy,json,tempfile,unittest,urllib.parse
from pathlib import Path
from drive_rotation import DriveRotation,OWNER,HEALTH_PARENT,RotationJournal,RotationStop

PARENT='syntheticparent123';OLD='syntheticold123';NEW='syntheticnew123';SHA='a'*64
class FakeDrive:
    def __init__(self):
        self.objects={};self.patches=[];self.lose_promote=False;self.lose_trash=False
        self.objects[PARENT]={'id':PARENT,'name':'HEALTH_SYNTHETIC_BACKUP_ROTATION_unit','mimeType':'application/vnd.google-apps.folder','parents':[],'trashed':False,'appProperties':{}}
        for id,state,sha,suffix in [(OLD,'ACTIVE','b'*64,'1234abcd'),(NEW,'CANDIDATE',SHA,'abcd1234')]:
            self.objects[id]={'id':id,'name':'complete-20261012T000000Z-'+suffix,'mimeType':'application/vnd.google-apps.folder','parents':[PARENT],'trashed':False,'appProperties':{'health_complete_set':'v1','health_archive_sha256':sha,'health_recovery_state':state}}
            file=id+'file';self.objects[file]={'id':file,'name':'complete-recovery.zip','mimeType':'application/zip','parents':[id],'trashed':False,'sha256Checksum':sha,'size':'20'}
        for m in self.objects.values():m.update(owners=[{'emailAddress':OWNER}],permissions=[{'type':'user','role':'owner','emailAddress':OWNER}])
    def request(self,path,method='GET',body=None,**kwargs):
        if path.startswith('/drive/v3/about'):return {'user':{'emailAddress':OWNER}}
        if path.startswith('/drive/v3/files?'):
            q=urllib.parse.parse_qs(urllib.parse.urlsplit(path).query)['q'][0];parent=q.split("'")[1]
            return {'files':[{'id':id} for id,m in self.objects.items() if m.get('parents')==[parent] and m.get('trashed') is False]}
        id=path.split('/')[4].split('?')[0];m=self.objects[id]
        if method=='PATCH':
            p=json.loads(body);self.patches.append((id,p))
            if 'appProperties' in p:m['appProperties'].update(p['appProperties'])
            if 'trashed' in p:m['trashed']=p['trashed']
            if id==NEW and self.lose_promote:self.lose_promote=False;raise RuntimeError('lost_promote_reply')
            if id==OLD and self.lose_trash:self.lose_trash=False;raise RuntimeError('lost_trash_reply')
        elif method!='GET':raise AssertionError('forbidden destructive API')
        return copy.deepcopy(m)

class RotationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.root.chmod(0o700)
        self.j=RotationJournal(self.root/'journal.sqlite');self.fake=FakeDrive();self.rotation=DriveRotation(self.fake,PARENT,self.j,test=True)
    def tearDown(self):self.j.close();self.temp.cleanup()
    def restore(self,id):
        self.assertEqual(id,NEW);self.assertFalse(self.fake.objects[OLD]['trashed'])
        return {'status':'ACTUAL_SYNTHETIC_SET_BYTES_READBACK_PASS','archive_sha256':SHA}
    def reopen(self):
        self.j.close();self.j=RotationJournal(self.root/'journal.sqlite');self.rotation=DriveRotation(self.fake,PARENT,self.j,test=True)
    def test_verified_new_before_old_trash(self):
        proof=self.rotation.promote(NEW,SHA,self.restore)
        self.assertEqual(self.fake.patches,[(NEW,{'appProperties':{'health_recovery_state':'ACTIVE'}}),(OLD,{'trashed':True})]);self.assertEqual(proof['permanent_deletes'],0)
    def test_failed_restore_preserves_old(self):
        with self.assertRaisesRegex(RotationStop,'restore_not_accepted'):self.rotation.promote(NEW,SHA,lambda id:{'status':'FAIL'})
        self.assertFalse(self.fake.objects[OLD]['trashed']);self.assertFalse(self.fake.patches)
    def test_changed_archive_after_restore_preserves_old(self):
        def restore(id):
            self.fake.objects[NEW+'file']['sha256Checksum']='c'*64
            return {'status':'ACTUAL_SYNTHETIC_SET_BYTES_READBACK_PASS','archive_sha256':SHA}
        with self.assertRaisesRegex(RotationStop,'current_archive_rejected'):self.rotation.promote(NEW,SHA,restore)
        self.assertFalse(self.fake.patches)
    def test_lost_promote_reply_reopen_does_not_trash_new(self):
        self.fake.lose_promote=True
        with self.assertRaisesRegex(RuntimeError,'lost_promote_reply'):self.rotation.promote(NEW,SHA,self.restore)
        self.assertFalse(self.fake.objects[OLD]['trashed']);self.reopen()
        self.rotation.promote(NEW,SHA,self.restore)
        self.assertFalse(self.fake.objects[NEW]['trashed']);self.assertTrue(self.fake.objects[OLD]['trashed'])
    def test_lost_trash_reply_reopen_recovers_exact_old_identity(self):
        self.fake.lose_trash=True
        with self.assertRaisesRegex(RuntimeError,'lost_trash_reply'):self.rotation.promote(NEW,SHA,self.restore)
        self.reopen()
        proof=self.rotation.promote(NEW,SHA,lambda id:{'status':'ACTUAL_SYNTHETIC_SET_BYTES_READBACK_PASS','archive_sha256':SHA})
        self.assertEqual(proof['previous_sets_trashed'],1);self.assertEqual(sum('trashed' in p for id,p in self.fake.patches),1)
    def test_old_archive_binding_change_is_preserved(self):
        def restore(id):
            self.fake.objects[OLD]['appProperties']['health_archive_sha256']='c'*64;self.fake.objects[OLD+'file']['sha256Checksum']='c'*64
            return {'status':'ACTUAL_SYNTHETIC_SET_BYTES_READBACK_PASS','archive_sha256':SHA}
        with self.assertRaisesRegex(RotationStop,'digest_binding_rejected'):self.rotation.promote(NEW,SHA,restore)
        self.assertFalse(self.fake.objects[OLD]['trashed'])
    def test_other_backup_copies_not_managed_are_preserved(self):
        m=copy.deepcopy(self.fake.objects[OLD]);m.update(id='unknownbackup123',name='historical-copy',appProperties={});self.fake.objects[m['id']]=m
        self.rotation.promote(NEW,SHA,self.restore);self.assertFalse(self.fake.objects[m['id']]['trashed'])
    def test_second_worker_denied(self):
        other=RotationJournal(self.root/'journal.sqlite')
        try:
            r=DriveRotation(self.fake,PARENT,other,test=True)
            with self.j.lock(),self.assertRaisesRegex(RotationStop,'concurrently_locked'):r.promote(NEW,SHA,self.restore)
        finally:other.close()
    def test_pending_rotation_blocks_another_target(self):
        with self.assertRaises(RotationStop):self.rotation.promote(NEW,SHA,lambda id:{})
        with self.assertRaisesRegex(RotationStop,'needs_reconciliation'):self.j.plan('anothertarget123',PARENT,SHA,[])
    def test_test_receipt_never_accepted_as_production_restore(self):
        self.rotation.test=False
        with self.assertRaisesRegex(RotationStop,'restore_not_accepted'):self.rotation.promote(NEW,SHA,self.restore)
        self.assertFalse(self.fake.patches)
    def test_foreign_sharing_rejected(self):
        self.fake.objects[PARENT]['permissions'].append({'role':'reader','type':'anyone'})
        with self.assertRaisesRegex(RotationStop,'owner_acl'):DriveRotation(self.fake,PARENT,self.j,test=True)
    def test_missing_acl_is_not_private_acl_evidence(self):
        self.fake.objects[PARENT].pop('permissions')
        with self.assertRaisesRegex(RotationStop,'owner_acl'):DriveRotation(self.fake,PARENT,self.j,test=True)
    def test_another_account_owned_folder_rejected(self):
        self.fake.objects[PARENT]['owners']=[{'emailAddress':'synthetic@example.invalid'}]
        with self.assertRaisesRegex(RotationStop,'owner_acl'):DriveRotation(self.fake,PARENT,self.j,test=True)
    def daily(self,stamp=True):
        self.fake.objects[PARENT].update(name='CompleteSets',parents=[HEALTH_PARENT],appProperties={'health_backup_pipeline':'v1','health_recovery_executor':'c'*64,'health_full_restore_archive':'d'*64} if stamp else {})
        return DriveRotation(self.fake,PARENT,self.j,verification='daily',executor_sha='c'*64)
    def daily_proof(self,id):
        return dict(status='ACTUAL_COMPLETE_ARCHIVE_DATABASE_AUTH_RESTORE_PASS',archive_sha256=SHA,all_members_verified=True,database_restore_pass=True,auth_http_pass=True,source_corpus_bytes_verified=True,source_graph_binding_verified=True,source_rebind_pass=False)
    def test_daily_requires_full_activation_of_same_executor(self):
        with self.assertRaisesRegex(RotationStop,'full_activation'):self.daily(stamp=False)
    def test_daily_reports_provider_recreation_not_run(self):
        result=self.daily().promote(NEW,SHA,self.daily_proof)
        self.assertEqual(result['previous_sets_trashed'],1)
    def test_daily_missing_source_byte_proof_preserves_old(self):
        proof=self.daily_proof(NEW);proof['source_corpus_bytes_verified']=False
        with self.assertRaisesRegex(RotationStop,'scope_incomplete'):self.daily().promote(NEW,SHA,lambda id:proof)
        self.assertFalse(self.fake.objects[OLD]['trashed'])
    def test_daily_missing_source_graph_binding_preserves_old(self):
        proof=self.daily_proof(NEW);proof['source_graph_binding_verified']=False
        with self.assertRaisesRegex(RotationStop,'scope_incomplete'):self.daily().promote(NEW,SHA,lambda id:proof)
        self.assertFalse(self.fake.objects[OLD]['trashed'])

if __name__=='__main__':unittest.main()
