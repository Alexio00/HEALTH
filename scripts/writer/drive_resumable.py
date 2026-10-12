"""Durable resumable upload candidate, restricted to disposable TEST folders.

Session URIs are private journal data. Only new files are created; production
folder wiring and SQL publication are not authorized by this adapter's success.
"""
from contextlib import contextmanager
import hashlib,json,os,re,sqlite3,urllib.error,urllib.parse,urllib.request
from pathlib import Path
from drive_provider import DriveError,DriveProvider,NoRedirect,identifier
from source_saga import SagaError,ResponseLost

CHUNK=4*1024*1024
MAX_SIZE=1024*1024*1024

def session_uri(value):
    try:
        u=urllib.parse.urlsplit(value);q=urllib.parse.parse_qs(u.query,strict_parsing=True,keep_blank_values=True)
        if u.scheme!='https' or u.hostname!='www.googleapis.com' or u.port not in (None,443) or u.username or u.password or u.fragment or u.path!='/upload/drive/v3/files':raise ValueError()
        if len(value)>16384 or set(q)-{'uploadType','upload_id','fields','session_crd'} or any(len(v)!=1 or not v[0] for v in q.values()) or q.get('uploadType')!=['resumable'] or not q.get('upload_id',[None])[0]:raise ValueError()
        if any(ord(c)<33 or ord(c)==127 for c in value):raise ValueError()
    except Exception:raise SagaError('resumable_session_origin_rejected') from None
    return value

def file_digest(path):
    path=Path(path)
    if path.is_symlink() or not path.is_file():raise SagaError('resumable_payload_not_regular_file')
    h=hashlib.sha256();size=0
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):
            size+=len(block)
            if size>MAX_SIZE:raise SagaError('resumable_size_limit')
            h.update(block)
    if size==0:raise SagaError('resumable_empty_payload_not_supported')
    return h.hexdigest(),size

class Wire:
    def __init__(self,token):
        self.token=token;self.opener=urllib.request.build_opener(NoRedirect)
    def request(self,url,method,body=b'',headers=None):
        if method=='PUT':session_uri(url)
        elif method!='POST' or url!='https://www.googleapis.com/upload/drive/v3/files?uploadType=resumable&fields=id':raise SagaError('resumable_request_not_allowlisted')
        allowed={'content-type','content-length','content-range','x-upload-content-type','x-upload-content-length'}
        if any(k.lower() not in allowed for k in (headers or {})):raise SagaError('resumable_header_rejected')
        values={'Authorization':'Bearer '+self.token(),**(headers or {})}
        req=urllib.request.Request(url,data=body,headers=values,method=method)
        try:
            with self.opener.open(req,timeout=90) as response:
                data=response.read(262145)
                if len(data)>262144:raise SagaError('resumable_metadata_response_too_large')
                return response.status,dict(response.headers),data
        except urllib.error.HTTPError as e:
            if e.code==308:return 308,dict(e.headers),b''
            raise DriveError(e.code) from None
        except (urllib.error.URLError,TimeoutError,OSError):raise ResponseLost('resumable_network_outcome_uncertain') from None
    def download_digest(self,object_id,expected_size):
        req=urllib.request.Request('https://www.googleapis.com/drive/v3/files/'+identifier(object_id)+'?alt=media',headers={'Authorization':'Bearer '+self.token()})
        h=hashlib.sha256();size=0
        try:
            with self.opener.open(req,timeout=90) as response:
                if response.status!=200:raise SagaError('resumable_readback_status_rejected')
                for block in iter(lambda:response.read(1024*1024),b''):
                    size+=len(block)
                    if size>expected_size:raise SagaError('resumable_readback_size_overflow')
                    h.update(block)
        except urllib.error.HTTPError as e:raise DriveError(e.code) from None
        except (urllib.error.URLError,TimeoutError,OSError):raise SagaError('resumable_readback_failed') from None
        if size!=expected_size:raise SagaError('resumable_readback_size_mismatch')
        return h.hexdigest(),size

class UploadJournal:
    def __init__(self,path):
        self.path=Path(path)
        if self.path.is_symlink() or self.path.parent.is_symlink() or not self.path.parent.is_dir():raise SagaError('private_upload_journal_path_rejected')
        if not self.path.exists():
            fd=os.open(self.path,os.O_RDWR|os.O_CREAT|os.O_EXCL,0o600);os.close(fd)
        if os.name!='nt' and (self.path.stat().st_mode&0o077 or self.path.parent.stat().st_mode&0o077):raise SagaError('private_upload_journal_permissions_required')
        self.db=sqlite3.connect(self.path);self.db.row_factory=sqlite3.Row
        self.db.execute('PRAGMA journal_mode=WAL');self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('CREATE TABLE IF NOT EXISTS resumable_uploads(marker TEXT PRIMARY KEY,folder TEXT NOT NULL,source_id TEXT NOT NULL,sha256 TEXT NOT NULL,size_bytes INTEGER NOT NULL,session_uri TEXT,object_id TEXT,state TEXT NOT NULL)');self.db.commit()
    def close(self):self.db.close()
    @contextmanager
    def lock(self,marker):
        if not re.fullmatch(r'[a-f0-9-]{32,36}',marker):raise SagaError('invalid_upload_correlation')
        path=self.path.parent/('upload-'+marker+'.lock')
        if path.is_symlink():raise SagaError('upload_lock_path_rejected')
        fd=os.open(path,os.O_RDWR|os.O_CREAT,0o600)
        file=os.fdopen(fd,'r+b',buffering=0)
        try:
            if os.fstat(fd).st_size==0:file.write(b'\0');file.seek(0)
            try:
                if os.name=='nt':
                    import msvcrt;msvcrt.locking(fd,msvcrt.LK_NBLCK,1)
                else:
                    import fcntl;fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except OSError:raise SagaError('upload_concurrently_locked') from None
            yield
        finally:file.close()
    def get(self,marker):
        row=self.db.execute('SELECT * FROM resumable_uploads WHERE marker=?',(marker,)).fetchone()
        return dict(row) if row else None
    def plan(self,marker,folder,source_id,sha,size):
        expected=(folder,source_id,sha,size)
        with self.db:
            row=self.get(marker)
            if row:
                if tuple(row[k] for k in ['folder','source_id','sha256','size_bytes'])!=expected:raise SagaError('resumable_payload_binding_changed')
            else:self.db.execute("INSERT INTO resumable_uploads VALUES(?,?,?,?,?,NULL,NULL,'PLANNED')",(marker,*expected))
        return self.get(marker)
    def session(self,marker,url):
        session_uri(url)
        with self.db:
            changed=self.db.execute("UPDATE resumable_uploads SET session_uri=?,state='SESSION' WHERE marker=? AND state='STARTING'",(url,marker)).rowcount
            if changed!=1:raise SagaError('resumable_session_transition_rejected')
    def starting(self,marker):
        with self.db:
            changed=self.db.execute("UPDATE resumable_uploads SET state='STARTING' WHERE marker=? AND state='PLANNED'",(marker,)).rowcount
            if changed!=1:raise SagaError('resumable_initiation_outcome_uncertain')
    def complete(self,marker,object_id):
        object_id=identifier(object_id)
        with self.db:
            row=self.get(marker)
            if not row or row['state'] not in ('SESSION','COMPLETE') or row['object_id'] not in (None,object_id):raise SagaError('resumable_completion_transition_rejected')
            self.db.execute("UPDATE resumable_uploads SET object_id=?,state='COMPLETE' WHERE marker=?",(object_id,marker))

def header(headers,name):return next((v for k,v in headers.items() if k.lower()==name.lower()),None)
def offset(headers,size):
    value=header(headers,'Range')
    if value is None:return 0
    match=re.fullmatch(r'bytes=0-([0-9]+)',value)
    if not match or not 0<int(match[1])+1<size:raise SagaError('resumable_range_rejected')
    return int(match[1])+1

class ResumableDriveProvider(DriveProvider):
    """New TEST folder or exact journal-bound recovery; unknown files stop recovery."""
    def __init__(self,folder,writer,verifier,journal,writer_wire,verifier_wire):
        self.folder=identifier(folder);self.writer=writer;self.verifier=verifier;self.created={}
        self.journal=journal;self.writer_wire=writer_wire;self.verifier_wire=verifier_wire
        meta=writer.request('/drive/v3/files/'+self.folder+'?fields=id,name,mimeType,trashed')
        if meta.get('mimeType')!='application/vnd.google-apps.folder' or meta.get('trashed') is not False or not re.fullmatch(r'HEALTH_SYNTHETIC_WRITER_[A-Za-z0-9_-]+',meta.get('name','')):raise SagaError('disposable_drive_folder_required')
        seen=set()
        for item in self.find_all():
            props=item.get('properties',{});marker=props.get('health_marker');row=journal.get(marker)
            if not row or row['folder']!=self.folder or row['state'] not in ('SESSION','COMPLETE') or not row['session_uri'] or row['object_id'] not in (None,item['id']) or marker in seen:raise SagaError('resume_inventory_outside_journal')
            checked=self.metadata(item['id'],writer)
            if props.get('health_source_id')!=row['source_id'] or int(checked['size'])!=row['size_bytes']:raise SagaError('resume_inventory_binding_changed')
            seen.add(marker);self.created[item['id']]=(marker,row['source_id'])
    def upload_file(self,marker,source_id,path,stop_after_chunks=None,lose_reply=False):
        if not re.fullmatch(r'[a-f0-9-]{32,36}',marker) or not re.fullmatch(r'SRC-[0-9]{8}-[0-9]{3,}',source_id):raise SagaError('invalid_upload_correlation')
        sha,size=file_digest(path)
        with self.journal.lock(marker):
            row=self.journal.plan(marker,self.folder,source_id,sha,size)
            if row['object_id']:return self._complete(marker,source_id,row['object_id'],size)
            if row['session_uri']:
                status,headers,data=self.writer_wire.request(row['session_uri'],'PUT',headers={'Content-Length':'0','Content-Range':'bytes */'+str(size)})
                if status in (200,201):return self._reply(marker,source_id,data,size)
                if status!=308:raise SagaError('resumable_status_rejected')
                start=offset(headers,size)
            else:
                self.journal.starting(marker)
                # SQL intent must already exist; this journal persists session before bytes.
                meta={'name':'synthetic-resumable-'+marker+'.bin','parents':[self.folder],'mimeType':'application/octet-stream','properties':{'health_marker':marker,'health_source_id':source_id,'health_synthetic':'true'}}
                status,headers,data=self.writer_wire.request('https://www.googleapis.com/upload/drive/v3/files?uploadType=resumable&fields=id','POST',json.dumps(meta).encode(),{'Content-Type':'application/json; charset=UTF-8','X-Upload-Content-Type':'application/octet-stream','X-Upload-Content-Length':str(size)})
                if status!=200:raise SagaError('resumable_initiation_rejected')
                url=session_uri(header(headers,'Location'));self.journal.session(marker,url);row=self.journal.get(marker);start=0
            chunks=0
            with Path(path).open('rb') as f:
                while start<size:
                    f.seek(start);block=f.read(min(CHUNK,size-start))
                    if not block:raise SagaError('resumable_local_file_changed')
                    end=start+len(block)-1
                    status,headers,data=self.writer_wire.request(row['session_uri'],'PUT',block,{'Content-Type':'application/octet-stream','Content-Length':str(len(block)),'Content-Range':f'bytes {start}-{end}/{size}'})
                    chunks+=1
                    if status in (200,201):
                        if end!=size-1:raise SagaError('resumable_completed_before_all_bytes')
                        # Lost final reply injection happens after real provider commit,
                        # before object identity is persisted in the local journal.
                        if lose_reply:raise ResponseLost('resumable_final_reply_lost')
                        if file_digest(path)!=(sha,size):raise SagaError('resumable_local_file_changed')
                        return self._reply(marker,source_id,data,size)
                    if status!=308:raise SagaError('resumable_chunk_status_rejected')
                    next_start=offset(headers,size)
                    if next_start<=start or next_start>end+1:raise SagaError('resumable_chunk_acknowledgement_rejected')
                    start=next_start
                    if stop_after_chunks is not None and chunks>=stop_after_chunks:raise ResponseLost('resumable_partial_workflow_stop')
            raise SagaError('resumable_missing_completion')
    def _reply(self,marker,source_id,data,size):
        try:object_id=json.loads(data)['id']
        except Exception:raise SagaError('resumable_completion_metadata_rejected') from None
        return self._complete(marker,source_id,object_id,size)
    def _complete(self,marker,source_id,object_id,size):
        meta=self.metadata(object_id,self.writer)
        props=meta['properties']
        if props.get('health_marker')!=marker or props.get('health_source_id')!=source_id or int(meta['size'])!=size:raise SagaError('resumable_completed_object_binding_rejected')
        self.journal.complete(marker,object_id);self.created[object_id]=(marker,source_id)
        return object_id
    def readback(self,object_id):
        before=self.metadata(object_id)
        sha,size=self.verifier_wire.download_digest(object_id,int(before['size']))
        after=self.metadata(object_id)
        if before!=after:raise SagaError('provider_changed_during_readback')
        props=before['properties']
        return {'object_id':object_id,'marker':props['health_marker'],'source_id':props['health_source_id']},sha,size
