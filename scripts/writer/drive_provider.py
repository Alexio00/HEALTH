"""Bounded synthetic Drive adapter. Never operates on an existing clinical folder.

Writer and verifier use distinct supplied transports; tokens are never logged.
Production provider configuration and resumable large uploads are not accepted.
"""
import hashlib
import json
import re
import urllib.error
import urllib.parse
import urllib.request
import uuid
from source_saga import ResponseLost, SagaError

class DriveError(SagaError):
    def __init__(self,status):
        self.status=status
        super().__init__('drive_http_'+str(status))

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        return None

class DriveTransport:
    def __init__(self,token):
        self.token=token
        self.opener=urllib.request.build_opener(NoRedirect)

    def request(self,path,method='GET',body=None,content_type=None,raw=False):
        if not path.startswith(('/drive/v3/','/upload/drive/v3/')) or method not in ('GET','POST','PATCH'):
            raise SagaError('drive_request_not_allowlisted')
        headers={'Authorization':'Bearer '+self.token()}
        if content_type: headers['Content-Type']=content_type
        req=urllib.request.Request('https://www.googleapis.com'+path,data=body,headers=headers,method=method)
        try:
            with self.opener.open(req,timeout=60) as reply:
                data=reply.read(6*1024*1024)
                if reply.read(1): raise SagaError('synthetic_adapter_response_too_large')
                return data if raw else json.loads(data)
        except urllib.error.HTTPError as error:
            raise DriveError(error.code) from None
        except (urllib.error.URLError,TimeoutError):
            raise SagaError('drive_network_outcome_uncertain') from None

def identifier(value):
    if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9_-]{8,128}',value):
        raise SagaError('invalid_provider_identity')
    return value

class DriveProvider:
    def __init__(self,folder,writer,verifier):
        self.folder=identifier(folder);self.writer=writer;self.verifier=verifier;self.created={}
        meta=writer.request('/drive/v3/files/'+self.folder+'?fields=id,name,mimeType,trashed')
        if meta.get('mimeType')!='application/vnd.google-apps.folder' or meta.get('trashed') is not False or not re.fullmatch(r'HEALTH_SYNTHETIC_WRITER_[A-Za-z0-9_-]+',meta.get('name','')):
            raise SagaError('disposable_drive_folder_required')
        if self.find_all(): raise SagaError('fresh_empty_drive_folder_required')

    def find_all(self):
        query="'"+self.folder+"' in parents and trashed = false"
        path='/drive/v3/files?'+urllib.parse.urlencode({'q':query,'fields':'files(id,properties),nextPageToken','pageSize':1000})
        page=self.verifier.request(path)
        if page.get('nextPageToken'): raise SagaError('synthetic_folder_inventory_overflow')
        return page.get('files',[])

    def create(self,marker,source_id,data,lose_reply=False,partial=False):
        if not re.fullmatch(r'[a-f0-9-]{32,36}',marker) or not re.fullmatch(r'SRC-[0-9]{8}-[0-9]{3,}',source_id):
            raise SagaError('invalid_upload_correlation')
        if len(data)>5*1024*1024: raise SagaError('synthetic_multipart_size_limit')
        metadata={'name':'synthetic-'+marker+'.bin','parents':[self.folder],'mimeType':'application/octet-stream',
                  'properties':{'health_marker':marker,'health_source_id':source_id,'health_synthetic':'true'}}
        boundary='health_'+uuid.uuid4().hex
        content=data[:max(1,len(data)//2)] if partial else data
        body=(('--'+boundary+'\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n').encode()+json.dumps(metadata).encode()
              +('\r\n--'+boundary+'\r\nContent-Type: application/octet-stream\r\n\r\n').encode()+content+('\r\n--'+boundary+'--\r\n').encode())
        response=self.writer.request('/upload/drive/v3/files?uploadType=multipart&fields=id',method='POST',body=body,content_type='multipart/related; boundary='+boundary)
        object_id=identifier(response['id']);self.created[object_id]=(marker,source_id)
        if lose_reply or partial: raise ResponseLost('upload_reply_lost')
        return object_id

    def find(self,marker):
        return [{'object_id':item['id'],'marker':marker,'source_id':item['properties'].get('health_source_id')}
                for item in self.find_all() if item.get('properties',{}).get('health_marker')==marker]

    def metadata(self,object_id,transport=None):
        object_id=identifier(object_id)
        meta=(transport or self.verifier).request('/drive/v3/files/'+object_id+'?fields=id,parents,properties,size,version,trashed,mimeType')
        if meta.get('parents')!=[self.folder] or meta.get('trashed') is not False or meta.get('properties',{}).get('health_synthetic')!='true':
            raise SagaError('provider_object_outside_disposable_scope')
        return meta

    def readback(self,object_id):
        before=self.metadata(object_id)
        data=self.verifier.request('/drive/v3/files/'+identifier(object_id)+'?alt=media',raw=True)
        after=self.metadata(object_id)
        if before!=after or int(before['size'])!=len(data):
            self.last_mismatch={'changed_fields':sorted(k for k in set(before)|set(after) if before.get(k)!=after.get(k)),
                                'metadata_size':int(before['size']),'readback_size':len(data)}
            raise SagaError('provider_changed_during_readback')
        props=before['properties']
        return {'object_id':object_id,'marker':props['health_marker'],'source_id':props['health_source_id']},hashlib.sha256(data).hexdigest(),len(data)

    def replace_created_for_test(self,object_id,data):
        meta=self.metadata(object_id,self.writer)
        props=meta['properties']
        if self.created.get(object_id)!=(props.get('health_marker'),props.get('health_source_id')):
            raise SagaError('refuse_mutation_of_uncreated_object')
        return self.writer.request('/upload/drive/v3/files/'+identifier(object_id)+'?uploadType=media&fields=id',
             method='PATCH',body=data,content_type='application/octet-stream')

    def trash_created(self):
        for object_id,binding in self.created.items():
            meta=self.metadata(object_id,self.writer);props=meta['properties']
            if binding!=(props.get('health_marker'),props.get('health_source_id')): raise SagaError('cleanup_identity_mismatch')
            result=self.writer.request('/drive/v3/files/'+object_id+'?fields=id,trashed',method='PATCH',body=b'{"trashed":true}',content_type='application/json')
            if result.get('trashed') is not True: raise SagaError('trash_readback_failed')
        if self.find_all(): raise SagaError('cleanup_unknown_objects_preserved')
        return self.writer.request('/drive/v3/files/'+self.folder+'?fields=id,trashed',method='PATCH',body=b'{"trashed":true}',content_type='application/json')
