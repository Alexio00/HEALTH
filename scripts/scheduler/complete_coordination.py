"""Hold a PostgreSQL shared session lock until DB and Source capture are sealed.

The session is independent of the shorter exported snapshot session. A live
backend/lock probe after every capture stage rejects silent session replacement.
No SQL data mutation; credentials live only in the existing protected transport.
"""
import json
import os
from pathlib import Path
from queue import Queue, Empty
import subprocess
import threading
from urllib.parse import urlsplit,unquote
from session_pooler_tls import install_ca,fields
from complete_sources import SourceStop

KEY=63741020261013
IMAGE='postgres@sha256:2d2b8998d31037bf721cfdf764d76ba74171b4fab3431b7f72c27c56ddbdf9e3'

class CaptureLock:
    def __init__(self,command,error_file,transport=None):
        self.command=command;self.error_file=error_file;self.process=None
        self.lines=Queue();self.mutex=threading.Lock();self.stop=threading.Event()
        self.errors=[];self.thread=None;self.pid=None;self.error_handle=None;self.transport=transport

    def query(self,sql):
        with self.mutex:
            if self.errors or self.process.poll() is not None:raise SourceStop('capture_coordination_session_lost')
            try:
                self.process.stdin.write(sql+'\n');self.process.stdin.flush()
                line=self.lines.get(timeout=30)
            except (Empty,OSError,ValueError):raise SourceStop('capture_coordination_probe_failed') from None
            if line is None:raise SourceStop('capture_coordination_session_lost')
            return line.strip()

    def assert_held(self):
        proof=json.loads(self.query("SELECT jsonb_build_object('pid',pg_backend_pid(),'held',EXISTS(SELECT 1 FROM pg_locks WHERE locktype='advisory' AND database=(SELECT oid FROM pg_database WHERE datname=current_database()) AND pid=pg_backend_pid() AND granted AND mode='ShareLock' AND objsubid=1 AND classid=(("+str(KEY)+"::bigint>>32)&4294967295)::oid AND objid=("+str(KEY)+"::bigint&4294967295)::oid));"))
        if proof['pid']!=self.pid or proof['held'] is not True:raise SourceStop('capture_coordination_binding_lost')

    def __enter__(self):
        self.error_handle=Path(self.error_file).open('x',encoding='utf-8')
        try:
            self.process=subprocess.Popen(self.command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.error_handle,text=True,encoding='utf-8')
            def read():
                for line in self.process.stdout:self.lines.put(line)
                self.lines.put(None)
            threading.Thread(target=read,daemon=True).start()
            proof=json.loads(self.query('SELECT jsonb_build_object(\'pid\',pg_backend_pid(),\'claimed\',pg_try_advisory_lock_shared('+str(KEY)+'));'))
            if proof['claimed'] is not True:raise SourceStop('source_writer_active_capture_not_started')
            self.pid=proof['pid'];self.assert_held()
            def heartbeat():
                while not self.stop.wait(10):
                    try:self.assert_held()
                    except Exception:self.errors.append('capture_coordination_session_lost');return
            self.thread=threading.Thread(target=heartbeat,daemon=True);self.thread.start()
            return self
        except Exception:
            self.close();raise

    def close(self):
        self.stop.set()
        if self.thread:self.thread.join(timeout=35)
        if self.process and self.process.poll() is None:
            try:
                self.process.stdin.write('\\q\n');self.process.stdin.flush();self.process.communicate(timeout=30)
            except Exception:
                self.process.terminate()
                try:self.process.wait(timeout=10)
                except subprocess.TimeoutExpired:self.process.kill();self.process.wait(timeout=10)
        if self.error_handle:self.error_handle.close()
        if self.transport:
            for file in ('pgpass','ca.pem'):
                path=Path(self.transport)/file
                if path.is_file() and not path.is_symlink():path.unlink()

    def __exit__(self,kind,value,trace):
        try:
            if kind is None:self.assert_held()
        finally:self.close()

def capture_lock(root):
    root=Path(root);inputs=root/'capture-coordination-transport';inputs.mkdir(mode=0o700)
    url=os.environ['SUPABASE_DB_URL'];p=urlsplit(url);role=unquote(p.username or '').split('.',1)[0]
    if role not in ('postgres','health_backup_reader'):raise SourceStop('approved_capture_reader_identity_required')
    if os.environ.get('HEALTH_REQUIRE_RESTRICTED_CAPTURE')=='1' and role!='health_backup_reader':raise SourceStop('restricted_capture_principal_required')
    install_ca(inputs/'ca.pem');fields(url,'ffvqgbslvjocbwfurxrv',role,(inputs/'ca.pem').resolve())
    def esc(value):return value.replace('\\','\\\\').replace(':','\\:')
    (inputs/'pgpass').write_text(':'.join(esc(value) for value in (p.hostname,'5432','postgres',unquote(p.username),unquote(p.password)))+'\n')
    (inputs/'pgpass').chmod(0o600)
    uid,gid=(65532,65532) if os.name=='nt' else (os.getuid(),os.getgid())
    command=['docker','run','-i','--rm','--pull=never','--read-only','--user',str(uid)+':'+str(gid),'--cap-drop=ALL','--security-opt=no-new-privileges',
      '--tmpfs',f'/private:rw,noexec,nosuid,nodev,mode=0700,uid={uid},gid={gid}','--mount','type=bind,source='+str(inputs.resolve())+',target=/run/input,readonly',
      '-e','PGHOST='+p.hostname,'-e','PGPORT=5432','-e','PGUSER='+unquote(p.username),'-e','PGDATABASE=postgres',
      '-e','PGSSLMODE=verify-full','-e','PGSSLROOTCERT=/run/input/ca.pem','-e','PGGSSENCMODE=disable','-e','PGPASSFILE=/private/pgpass','-e','PGCONNECT_TIMEOUT=15',
      '-e','PGOPTIONS=-c default_transaction_read_only=on','--entrypoint','sh',IMAGE,'-c',
      'cp /run/input/pgpass /private/pgpass && chmod 600 /private/pgpass && exec "$@"','health-private',
      'psql','-X','-q','-A','-t','-v','ON_ERROR_STOP=1']
    return CaptureLock(command,root/'capture-coordination.private.stderr',inputs)
