"""SQL journal adapter using one persistent Session-pooler DB-API connection.

The caller supplies a restricted connection. No connection string, URL, SQL
parameters or database exception text is logged. Use the approved TLS helper
for a Supabase connection; transaction pooling is not supported for this lock.
"""
from contextlib import contextmanager
import json,re
from drive_resumable import session_uri
from source_saga import SagaError

class PostgresUploadJournal:
    def __init__(self,connection,schema='health_writer'):
        if not re.fullmatch(r'health_writer(?:_fixture_[a-z0-9]{8,32})?',schema):
            raise SagaError('upload_journal_schema_rejected')
        self.connection=connection;self.schema=schema;self.held=set()
        connection.autocommit=True
    def _call(self,function,*args):
        try:
            with self.connection.cursor() as cursor:
                cursor.execute('SELECT '+self.schema+'.upload_'+function+'('+','.join(['%s']*len(args))+');',args)
                value=cursor.fetchone()[0]
            if value=='':return None  # libpq represents PostgreSQL void as ''.
            return json.loads(value) if isinstance(value,str) else value
        except Exception as error:
            code=getattr(error,'pgcode',None) or getattr(error,'sqlstate',None)
            if not isinstance(code,str) or not re.fullmatch('[0-9A-Z]{5}',code):code='UNAVAILABLE'
            raise SagaError('upload_journal_sqlstate_'+code) from None
    @contextmanager
    def lock(self,marker):
        if not re.fullmatch(r'[a-f0-9-]{32,36}',marker):raise SagaError('invalid_upload_correlation')
        if marker in self.held:raise SagaError('upload_journal_reentrant_lock_rejected')
        if self._call('claim',marker) is not True:raise SagaError('upload_concurrently_locked')
        self.held.add(marker)
        try:yield
        finally:
            self.held.remove(marker)
            if not self.connection.closed:
                if self._call('release',marker) is not True:raise SagaError('upload_journal_lock_release_failed')
    def get(self,marker):return self._call('get',marker)
    def plan(self,marker,folder,source_id,sha,size):return self._call('plan',marker,folder,source_id,sha,size)
    def starting(self,marker):self._call('starting',marker)
    def authorize(self,marker):self._call('authorize',marker)
    def description(self,marker):return self._call('description',marker)
    def session(self,marker,url):self._call('session',marker,session_uri(url))
    def complete(self,marker,object_id):self._call('complete',marker,object_id)
    def close(self):self.connection.close()
