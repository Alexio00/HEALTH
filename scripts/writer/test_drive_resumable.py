"""Fault injection tests: durable recovery, object binding, no foreign credentials."""
import hashlib,json,os,tempfile,unittest,uuid
from pathlib import Path
from drive_resumable import CHUNK,ResumableDriveProvider,UploadJournal,Wire,offset,session_uri
from source_saga import SagaError,ResponseLost

FOLDER='syntheticfolder123'
URI='https://www.googleapis.com/upload/drive/v3/files?uploadType=resumable&upload_id=synthetic'

class Fake:
    def __init__(self):
        self.files={};self.data=bytearray();self.posts=0;self.puts=0;self.meta=None;self.lose_start=False;self.journal=None
    def request(self,url,method='GET',body=None,headers=None,**kwargs):
        if method=='POST':
            self.posts+=1;self.meta=json.loads(body)
            if self.lose_start:raise ResponseLost('synthetic_start_response_lost')
            return 200,{'Location':URI},b''
        if method=='PUT':
            self.puts+=1
            # Verify another connection can see the durable session before data.
            probe=UploadJournal(self.journal.path)
            try:assert probe.get(self.meta['properties']['health_marker'])['session_uri']==URI
            finally:probe.close()
            total=int(headers['Content-Range'].split('/')[-1])
            if body:
                start=int(headers['Content-Range'].split(' ')[1].split('-')[0]);assert start==len(self.data)
                self.data.extend(body)
            if len(self.data)==total:
                self.files['syntheticobject123']={'id':'syntheticobject123','parents':[FOLDER],'properties':self.meta['properties'],'size':str(total),'version':'1','trashed':False,'mimeType':'application/octet-stream'}
                return 200,{},b'{"id":"syntheticobject123"}'
            return 308,({'Range':'bytes=0-'+str(len(self.data)-1)} if self.data else {}),b''
        if url.startswith('/drive/v3/files?'):return {'files':[{'id':k,'properties':v['properties']} for k,v in self.files.items()]}
        if url.startswith('/drive/v3/files/'+FOLDER):return {'id':FOLDER,'name':'HEALTH_SYNTHETIC_WRITER_unit','mimeType':'application/vnd.google-apps.folder','trashed':False}
        object_id=url.split('/')[4].split('?')[0]
        return dict(self.files[object_id])
    def download_digest(self,object_id,size):
        assert size==len(self.data)
        return hashlib.sha256(self.data).hexdigest(),len(self.data)

class Recovery(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        if os.name!='nt':self.root.chmod(0o700)
        self.j=UploadJournal(self.root/'journal.sqlite');self.fake=Fake();self.fake.journal=self.j
        self.marker=uuid.uuid4().hex;self.src='SRC-20261012-001'
        self.path=self.root/'payload';self.path.write_bytes(b'a'*CHUNK+b'b'*CHUNK+b'c'*111)
        self.provider=self.open_provider()
    def tearDown(self):self.j.close();self.temp.cleanup()
    def open_provider(self):return ResumableDriveProvider(FOLDER,self.fake,self.fake,self.j,self.fake,self.fake)
    def reopen(self):
        self.j.close();self.j=UploadJournal(self.root/'journal.sqlite');self.fake.journal=self.j;self.provider=self.open_provider()
    def test_partial_close_reopen_and_final_reply_loss(self):
        with self.assertRaises(ResponseLost):self.provider.upload_file(self.marker,self.src,self.path,stop_after_chunks=1)
        self.assertEqual(len(self.fake.data),CHUNK);self.reopen()
        with self.assertRaises(ResponseLost):self.provider.upload_file(self.marker,self.src,self.path,lose_reply=True)
        self.assertEqual(self.j.get(self.marker)['state'],'SESSION');self.reopen()
        identity=self.provider.upload_file(self.marker,self.src,self.path)
        self.assertEqual(self.fake.posts,1);self.assertEqual(len(self.fake.files),1)
        self.assertEqual(self.provider.readback(identity)[1],hashlib.sha256(self.path.read_bytes()).hexdigest())
        puts=self.fake.puts;self.assertEqual(self.provider.upload_file(self.marker,self.src,self.path),identity);self.assertEqual(self.fake.puts,puts)
    def test_changed_payload_replay_stops_before_network(self):
        with self.assertRaises(ResponseLost):self.provider.upload_file(self.marker,self.src,self.path,stop_after_chunks=1)
        calls=self.fake.puts;self.path.write_bytes(b'changed')
        with self.assertRaisesRegex(SagaError,'binding_changed'):self.provider.upload_file(self.marker,self.src,self.path)
        self.assertEqual(self.fake.puts,calls)
    def test_lost_initiation_never_creates_second_session(self):
        self.fake.lose_start=True
        with self.assertRaises(ResponseLost):self.provider.upload_file(self.marker,self.src,self.path)
        self.reopen()
        with self.assertRaisesRegex(SagaError,'initiation_outcome_uncertain'):self.provider.upload_file(self.marker,self.src,self.path)
        self.assertEqual(self.fake.posts,1)
    def test_foreign_inventory_preserved(self):
        self.fake.files['unknownobject123']={'id':'unknownobject123','properties':{'health_marker':uuid.uuid4().hex}}
        with self.assertRaisesRegex(SagaError,'outside_journal'):self.open_provider()
    def test_renamed_source_on_completed_object_rejected(self):
        identity=self.provider.upload_file(self.marker,self.src,self.path)
        self.fake.files[identity]['properties']['health_source_id']='SRC-20261012-002'
        with self.assertRaisesRegex(SagaError,'binding_changed'):self.open_provider()
    def test_duplicate_remote_marker_rejected(self):
        identity=self.provider.upload_file(self.marker,self.src,self.path)
        other=dict(self.fake.files[identity]);other['id']='duplicateobject123';self.fake.files[other['id']]=other
        with self.assertRaisesRegex(SagaError,'outside_journal'):self.open_provider()
    def test_second_worker_lock_denied(self):
        second=UploadJournal(self.root/'journal.sqlite')
        try:
            with self.j.lock(self.marker):
                with self.assertRaisesRegex(SagaError,'concurrently_locked'):
                    with second.lock(self.marker):pass
        finally:second.close()
    def test_completion_identity_cannot_be_rebound(self):
        self.provider.upload_file(self.marker,self.src,self.path)
        with self.assertRaisesRegex(SagaError,'completion_transition'):self.j.complete(self.marker,'differentobject123')

class Boundary(unittest.TestCase):
    def test_origin_before_token_or_network(self):
        samples=[URI.replace('www.googleapis.com','attacker.invalid'),URI.replace('https:','http:'),URI.replace('www.googleapis.com','www.googleapis.com@attacker.invalid'),URI+'&upload_id=second',URI+'#fragment',URI+'&unexpected=x',URI.replace('www.googleapis.com','www.googleapis.com:444'),URI.replace('https:','https:\t')]
        def forbidden():raise AssertionError('credential was accessed')
        wire=Wire(forbidden)
        for value in samples:
            with self.subTest(value=value),self.assertRaises(SagaError):wire.request(value,'PUT')
        with self.assertRaisesRegex(SagaError,'header_rejected'):wire.request(URI,'PUT',headers={'Authorization':'override'})
    def test_provider_range_not_client_guess(self):
        self.assertEqual(session_uri(URI+'&session_crd=synthetic'),URI+'&session_crd=synthetic')
        self.assertEqual(offset({'rAnGe':'bytes=0-1023'},4096),1024)
        self.assertEqual(offset({},4096),0)
        for value in ['bytes=1-100','bytes=0-4095','bytes=0-9999','bytes=0--1','garbage']:
            with self.subTest(value=value),self.assertRaises(SagaError):offset({'Range':value},4096)

if __name__=='__main__':unittest.main()
