"""Actual restricted PG17 TCP journal with a simulated resumable Drive wire.

Synthetic fixture only. Semantic approvals are simulated; no clinical or
production acceptance is inferred from this suite.
"""
import argparse,hashlib,json,os,tempfile
from pathlib import Path
import psycopg2
from postgres_upload_journal import PostgresUploadJournal
from drive_resumable import CHUNK,ResumableDriveProvider
from source_saga import SagaError,ResponseLost
from test_durable import run,HERE
from test_source_integration import literal,document
from test_drive_resumable import Fake,FOLDER,URI

class SQLWire(Fake):
    def request(self,url,method='GET',body=None,headers=None,**kwargs):
        if method!='PUT':return super().request(url,method,body,headers,**kwargs)
        self.puts+=1
        probe=self.probe()
        try:assert probe.get(self.meta['properties']['health_marker'])['session_uri']==URI
        finally:probe.close()
        total=int(headers['Content-Range'].split('/')[-1])
        if body:
            start=int(headers['Content-Range'].split(' ')[1].split('-')[0]);assert start==len(self.data)
            self.data.extend(body)
            if hasattr(self,'after_chunk'):self.after_chunk()
        if len(self.data)==total:
            self.files['syntheticobject123']={'id':'syntheticobject123','parents':[FOLDER],
                'properties':self.meta['properties'],'size':str(total),'version':'1',
                'trashed':False,'mimeType':'application/octet-stream'}
            return 200,{},b'{"id":"syntheticobject123"}'
        return 308,({'Range':'bytes=0-'+str(len(self.data)-1)} if self.data else {}),b''

def suite(ctx,host,port,database):
    s=ctx['schema'];execute=ctx['execute'];check=ctx['check'];key='postgres_upload'
    execute('BEGIN;'+(HERE/'source_runtime.sql').read_text().replace('__SCHEMA__',s)
            +(HERE/'resumable_runtime.sql').read_text().replace('__SCHEMA__',s)+'COMMIT;')
    execute(f"INSERT INTO {s}.upload_folders VALUES('{FOLDER}',true);")
    ctx['intent'](key);ctx['api']('prepare',key)
    journals=[]
    def journal(role=0):
        connection=psycopg2.connect(host=host,port=port,dbname=database,
            user=ctx['roles'][role],password=ctx['passwords'][role],connect_timeout=10,sslmode='disable')
        j=PostgresUploadJournal(connection,s);journals.append(j);return j
    def denied(label,fn,code='P0001'):
        try:fn()
        except SagaError as error:check(label,str(error)=='upload_journal_sqlstate_'+code)
        else:raise RuntimeError('expected_denial:'+label)
    def plan(number,payload):
        row={'source_id':'SRC-20261012-'+str(800+number),'logical_path':'synthetic/pg-upload-'+str(number),
             'original_filename':'synthetic.bin','mime_type':'application/octet-stream',
             'sha256':hashlib.sha256(payload).hexdigest(),'size_bytes':len(payload),
             'created_at':execute('SELECT clock_timestamp();'),'metadata':{'test_only':True}}
        planned=json.loads(execute(f"SELECT {s}.plan_source({literal(key)},{document(row)},'gdrive','synthetic');",0))
        execute(f"SELECT {s}.source_uncertain({literal(key)},{literal(row['source_id'])});",0)
        return row,planned['marker']
    try:
        payload=b'a'*CHUNK+b'b'*CHUNK+b'c'*123
        row,marker=plan(1,payload);j=journal();other=journal();foreign=journal(1)
        check('journal_actual_restricted_tcp',not j.connection.closed)
        for table in ('source_upload_sessions','upload_folders'):
            check('journal_writer_direct_'+table+'_denied',execute(f'DELETE FROM {s}.{table};',0,'42501'),sqlstate='42501')
        check('journal_private_guard_denied',execute(f"SELECT {s}.upload_guard('{marker}',false,false);",0,'42501'))
        denied('journal_foreign_get_denied',lambda:foreign.get(marker),'42501')
        denied('journal_mutation_without_worker_lock_denied',lambda:j.plan(marker,FOLDER,row['source_id'],row['sha256'],row['size_bytes']))
        with other.connection.cursor() as cursor:
            cursor.execute('SELECT pg_try_advisory_lock_shared(63741020261013)');assert cursor.fetchone()[0]
        try:
            with j.lock(marker):raise RuntimeError('upload_wrote_during_backup_capture')
        except SagaError as error:check('journal_shared_backup_capture_blocks_source_upload',str(error)=='upload_concurrently_locked')
        with other.connection.cursor() as cursor:
            cursor.execute('SELECT pg_advisory_unlock_shared(63741020261013)');assert cursor.fetchone()[0]
        with j.lock(marker):
            first=j.plan(marker,FOLDER,row['source_id'],row['sha256'],row['size_bytes'])
            check('journal_plan_exact_source_and_marker',first['marker']==marker and first['state']=='PLANNED')
            denied('journal_changed_sha_denied',lambda:j.plan(marker,FOLDER,row['source_id'],'f'*64,row['size_bytes']))
            denied('journal_changed_size_denied',lambda:j.plan(marker,FOLDER,row['source_id'],row['sha256'],row['size_bytes']+1))
            denied('journal_changed_folder_denied',lambda:j.plan(marker,'foreignfolder123',row['source_id'],row['sha256'],row['size_bytes']))
            try:
                with other.lock(marker):raise RuntimeError('second_worker_acquired_lock')
            except SagaError as error:check('journal_second_session_lock_denied',str(error)=='upload_concurrently_locked')
            j.starting(marker)
            for index,url in enumerate([URI.replace('www.googleapis.com','example.org'),URI+'&unknown=x',URI+'&upload_id=again',URI+'#fragment',URI+'&session_crd=a&session_crd=b']):
                denied('journal_server_rejects_bad_session_'+str(index),lambda url=url:j._call('session',marker,url))
            j.session(marker,URI)
            check('journal_session_durable_in_independent_connection',other.get(marker)['session_uri']==URI)
        j.close()
        with other.lock(marker):
            check('journal_new_worker_resumes_same_session',other.get(marker)['session_uri']==URI)
            other.complete(marker,'syntheticobject123')
            other.complete(marker,'syntheticobject123')
            denied('journal_object_rebinding_denied',lambda:other.complete(marker,'differentobject123'))
        check('journal_transport_complete_does_not_attest_source',execute(f"SELECT state FROM {s}.source_uploads WHERE marker='{marker}';")=='UNCERTAIN')
        row,marker=plan(2,payload);path=None;wire=SQLWire();wire.probe=journal
        with tempfile.TemporaryDirectory(prefix='health-sql-upload-') as tmp:
            path=Path(tmp)/'synthetic.bin';path.write_bytes(payload)
            j=journal();provider=ResumableDriveProvider(FOLDER,wire,wire,j,wire,wire)
            try:provider.upload_file(marker,row['source_id'],path,stop_after_chunks=1)
            except ResponseLost:pass
            check('journal_chunk_pause_has_durable_session',len(wire.data)==CHUNK and j.get(marker)['state']=='SESSION')
            j.close();j=journal();provider=ResumableDriveProvider(FOLDER,wire,wire,j,wire,wire)
            try:provider.upload_file(marker,row['source_id'],path,lose_reply=True)
            except ResponseLost:pass
            check('journal_lost_final_reply_keeps_session',j.get(marker)['state']=='SESSION' and len(wire.files)==1)
            j.close();j=journal();provider=ResumableDriveProvider(FOLDER,wire,wire,j,wire,wire)
            object_id=provider.upload_file(marker,row['source_id'],path)
            check('journal_new_db_session_recovers_same_remote_object',object_id=='syntheticobject123' and wire.posts==1)
            check('journal_independent_full_byte_digest',provider.readback(object_id)[1:]==(row['sha256'],row['size_bytes']))
            puts=wire.puts;check('journal_replay_sends_no_upload',provider.upload_file(marker,row['source_id'],path)==object_id and wire.puts==puts)
            row,marker=plan(3,b'synthetic-initiation-loss');path.write_bytes(b'synthetic-initiation-loss')
            wire=SQLWire();wire.probe=journal;wire.lose_start=True
            provider=ResumableDriveProvider(FOLDER,wire,wire,j,wire,wire)
            try:provider.upload_file(marker,row['source_id'],path)
            except ResponseLost:pass
            check('journal_lost_initiation_is_durable_starting',j.get(marker)['state']=='STARTING')
            j.close();j=journal();provider=ResumableDriveProvider(FOLDER,wire,wire,j,wire,wire)
            denied('journal_restart_does_not_create_second_session',lambda:provider.upload_file(marker,row['source_id'],path))
            check('journal_lost_initiation_one_post',wire.posts==1)
            row,marker=plan(4,payload);path.write_bytes(payload)
            wire=SQLWire();wire.probe=journal
            wire.after_chunk=lambda:execute(f"UPDATE {s}.writer_intents SET approved=false WHERE request_key='{key}';")
            provider=ResumableDriveProvider(FOLDER,wire,wire,j,wire,wire)
            denied('journal_revocation_blocks_next_external_chunk',lambda:provider.upload_file(marker,row['source_id'],path))
            check('journal_revocation_preserves_partial_session',len(wire.data)==CHUNK and j.get(marker)['state']=='SESSION')
            execute(f"UPDATE {s}.writer_intents SET approved=true WHERE request_key='{key}'; UPDATE {s}.upload_folders SET enabled=false;")
            denied('journal_disabled_folder_blocks_status_and_chunks',lambda:provider.upload_file(marker,row['source_id'],path))
            check('journal_disabled_folder_sent_no_request',wire.posts==1 and wire.puts==1)
            execute(f"UPDATE {s}.upload_folders SET enabled=true;")
        ctx['api']('abandon',key)
        with j.lock(marker):denied('journal_abandoned_operation_cannot_upload',lambda:j.starting(marker))
    finally:
        for j in journals:
            if not j.connection.closed:j.close()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--docker-container');p.add_argument('--port',type=int,default=5432)
    p.add_argument('--database',default='postgres');p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    try:
        proof=run(a.docker_container,a.database,lambda ctx:suite(ctx,'127.0.0.1',a.port,a.database))
        proof.update(status='RESTRICTED_TCP_SQL_RESUMABLE_JOURNAL_PASS',drive_wire='SIMULATED',
            sql_journal='ACTUAL_POSTGRES_17_TCP',source_saga='JOURNAL_ONLY_PUBLICATION_NOT_TESTED',
            cleanup='unique fixture schema and logins removed')
        a.out.write_text(json.dumps(proof,indent=2));print(json.dumps({k:v for k,v in proof.items() if k!='checks'}))
    except Exception as error:
        proof={'status':'STOPPED','safe_reason':str(error) if isinstance(error,(RuntimeError,SagaError)) else type(error).__name__}
        a.out.write_text(json.dumps(proof,indent=2));print(json.dumps(proof));raise SystemExit(2)
