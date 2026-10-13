"""Create-only Source uploads backed by the restricted, authoritative SQL intent.

The registered folder is checked against owner/verifier identities and actual
write capability. No existing inventory, file update or purge method is used.
Publication still requires the separate Source verifier RPC and candidate.
"""
import os,re,urllib.parse
from drive_provider import identifier
from drive_resumable import ResumableDriveProvider,Wire
from postgres_upload_journal import PostgresUploadJournal
from source_saga import SagaError

OWNER=os.environ.get('HEALTH_SOURCE_OWNER_EMAIL','')
VERIFIER=os.environ.get('HEALTH_SOURCE_VERIFIER_EMAIL','')

class SourceDriveProvider(ResumableDriveProvider):
    def __init__(self,folder,writer,verifier,journal,writer_wire=None,verifier_wire=None):
        if not isinstance(journal,PostgresUploadJournal):raise SagaError('source_sql_journal_required')
        if not OWNER or not VERIFIER or OWNER==VERIFIER:raise SagaError('source_account_configuration_required')
        self.folder=identifier(folder);self.writer=writer;self.verifier=verifier;self.journal=journal;self.created={}
        self.writer_wire=writer_wire or Wire(writer.token);self.verifier_wire=verifier_wire or Wire(verifier.token)
        if writer.request('/drive/v3/about?fields=user(emailAddress)')['user']['emailAddress']!=OWNER:
            raise SagaError('source_owner_identity_rejected')
        if verifier.request('/drive/v3/about?fields=user(emailAddress)')['user']['emailAddress']!=VERIFIER:
            raise SagaError('source_verifier_identity_rejected')
        meta=writer.request('/drive/v3/files/'+self.folder+'?fields=id,mimeType,owners(emailAddress),capabilities(canAddChildren),trashed')
        if (meta.get('id')!=self.folder or meta.get('owners')!=[{'emailAddress':OWNER}]
            or meta.get('mimeType')!='application/vnd.google-apps.folder' or meta.get('trashed') is not False
            or meta.get('capabilities',{}).get('canAddChildren') is not True):
            raise SagaError('source_owner_folder_rejected')
        other=verifier.request('/drive/v3/files/'+self.folder+'?fields=id,capabilities(canAddChildren),trashed')
        if other.get('id')!=self.folder or other.get('trashed') is not False or other.get('capabilities',{}).get('canAddChildren') is not False:
            raise SagaError('source_independent_reader_scope_rejected')
    def _upload_metadata(self,marker,source_id):
        row=self.journal.description(marker);name=row.get('logical_path');mime=row.get('mime_type') or 'application/octet-stream'
        if (row.get('source_id')!=source_id or not isinstance(name,str) or not 1<=len(name)<=200
            or name in ('.','..') or any(c in name for c in '/\\\x00\r\n')
            or any(ord(c)<32 for c in name) or not isinstance(mime,str)
            or not re.fullmatch(r'[a-zA-Z0-9!#$&^_.+-]+/[a-zA-Z0-9!#$&^_.+-]+',mime)
            or mime.startswith('application/vnd.google-apps.')):
            raise SagaError('source_name_or_mime_rejected')
        # A different correlated object with the same path is an identity conflict.
        query="'"+self.folder+"' in parents and trashed=false and name='"+name.replace('\\','\\\\').replace("'","\\'")+"'"
        existing=self.verifier.request('/drive/v3/files?'+urllib.parse.urlencode({'q':query,'fields':'files(id),nextPageToken','pageSize':2}))
        if existing.get('files') or existing.get('nextPageToken'):raise SagaError('source_path_already_exists_reconcile_required')
        return {'name':name,'parents':[self.folder],'mimeType':mime,'properties':{
            'health_marker':marker,'health_source_id':source_id,'health_writer_protocol':'v1'}}
    def find(self,marker):
        if not re.fullmatch(r'[a-f0-9-]{32,36}',marker):raise SagaError('invalid_upload_correlation')
        row=self.journal.get(marker)
        if not row or row['folder']!=self.folder:raise SagaError('source_folder_binding_rejected')
        query="'"+self.folder+"' in parents and trashed=false and properties has {key='health_marker' and value='"+marker+"'}"
        data=self.verifier.request('/drive/v3/files?'+urllib.parse.urlencode({'q':query,'fields':'files(id,properties),nextPageToken','pageSize':2}))
        if data.get('nextPageToken') or len(data.get('files',[]))>1:raise SagaError('source_marker_ambiguous')
        results=[]
        for item in data.get('files',[]):
            meta=self.metadata(item['id']);props=meta['properties']
            if props.get('health_marker')!=marker or props.get('health_source_id')!=row['source_id']:
                raise SagaError('source_marker_binding_rejected')
            results.append({'object_id':item['id'],'marker':marker,'source_id':row['source_id']})
        return results
    def metadata(self,object_id,transport=None):
        object_id=identifier(object_id)
        meta=(transport or self.verifier).request('/drive/v3/files/'+object_id+'?fields=id,parents,properties,size,version,trashed,mimeType')
        props=meta.get('properties',{});marker=props.get('health_marker')
        if props.get('health_writer_protocol')!='v1' or not isinstance(marker,str) or not re.fullmatch(r'[a-f0-9-]{32,36}',marker):
            raise SagaError('source_protocol_object_required')
        row=self.journal.get(marker)
        if (not row or row['folder']!=self.folder or props.get('health_source_id')!=row['source_id']
            or row['object_id'] not in (None,object_id) or meta.get('id')!=object_id
            or meta.get('parents')!=[self.folder] or meta.get('trashed') is not False
            or int(meta.get('size',-1))!=row['size_bytes']):
            raise SagaError('source_object_sql_binding_rejected')
        return meta
    def create(self,*args,**kwargs):raise SagaError('source_requires_sql_resumable_upload')
    def find_all(self):raise SagaError('source_unbounded_inventory_rejected')
    def replace_created_for_test(self,*args,**kwargs):raise SagaError('source_file_replacement_forbidden')
    def trash_created(self):raise SagaError('source_file_purge_requires_separate_owner_protocol')

class SourceUploader(SourceDriveProvider):
    """Upload worker holds no independent-reader/backup credential.

    Owner metadata is sufficient to recover its own transport outcome. It is
    never evidence of an independent byte check or authority to publish Source.
    """
    def __init__(self,folder,writer,journal,writer_wire=None):
        if not isinstance(journal,PostgresUploadJournal):raise SagaError('source_sql_journal_required')
        self.folder=identifier(folder);self.writer=writer;self.verifier=writer;self.journal=journal;self.created={}
        self.writer_wire=writer_wire or Wire(writer.token);self.verifier_wire=None
        if writer.request('/drive/v3/about?fields=user(emailAddress)')['user']['emailAddress']!=OWNER:raise SagaError('source_owner_identity_rejected')
        meta=writer.request('/drive/v3/files/'+self.folder+'?fields=id,mimeType,owners(emailAddress),capabilities(canAddChildren),trashed')
        if meta.get('id')!=self.folder or meta.get('owners')!=[{'emailAddress':OWNER}] or meta.get('mimeType')!='application/vnd.google-apps.folder' or meta.get('trashed') is not False or meta.get('capabilities',{}).get('canAddChildren') is not True:raise SagaError('source_owner_folder_rejected')
    def readback(self,*args,**kwargs):raise SagaError('independent_source_verifier_required')
