"""Exact project/role, CA-pinned Session transport; no clinical SQL or URL output."""
import argparse
from contextlib import contextmanager
import hashlib,json,os,re,subprocess,tempfile
from pathlib import Path
from urllib.parse import parse_qs,unquote,urlsplit

CA_SHA='700723581420dd1ac98fd7e9ac529f0ef210eadcaf87fc868a3ad7d114c2f3b7'
POLICIES={'ffvqgbslvjocbwfurxrv':{'postgres','health_backup_reader','health_writer'},'yjmcesdayfmfissghzgm':{'health_test_ci'}}
class SafeStop(RuntimeError):pass

def install_ca(destination):
    data=os.environ.get('HEALTH_SUPABASE_CA_PEM','').replace('\r\n','\n').strip()+'\n'
    if hashlib.sha256(data.encode()).hexdigest()!=CA_SHA:raise SafeStop('trusted_ca_pin_mismatch')
    destination=Path(destination)
    with destination.open('x',encoding='utf-8',newline='\n') as f:f.write(data)
    destination.chmod(0o600)

def fields(uri,project,role,ca):
    try:
        if project not in POLICIES or role not in POLICIES[project]:raise ValueError()
        u=urlsplit(uri);q=parse_qs(u.query,strict_parsing=True,keep_blank_values=True)
        if u.scheme not in ('postgres','postgresql') or u.fragment or u.port not in (None,5432) or u.path!='/postgres':raise ValueError()
        if not re.fullmatch(r'aws-[0-9]+-us-west-1\.pooler\.supabase\.com',u.hostname or ''):raise ValueError()
        if project=='ffvqgbslvjocbwfurxrv' and u.hostname!='aws-0-us-west-1.pooler.supabase.com':raise ValueError()
        if unquote(u.username or '')!=role+'.'+project or not u.password:raise ValueError()
        if set(q)-{'sslmode','sslrootcert','gssencmode','connect_timeout','application_name'} or any(len(v)!=1 for v in q.values()):raise ValueError()
        if q.get('sslmode',['require'])[0] not in ('require','verify-ca','verify-full') or q.get('gssencmode',['disable'])[0]!='disable':raise ValueError()
        password=unquote(u.password)
        if any(c in password for c in '\r\n\x00') or any(c in uri for c in '\r\n\x00'):raise ValueError()
        ca=Path(ca)
        if not ca.is_absolute() or ca.is_symlink() or not ca.is_file() or hashlib.sha256(ca.read_bytes()).hexdigest()!=CA_SHA:raise ValueError()
        return {'PGHOST':u.hostname,'PGPORT':'5432','PGUSER':unquote(u.username),'PGDATABASE':'postgres',
         'PGSSLMODE':'verify-full','PGSSLROOTCERT':str(ca),'PGGSSENCMODE':'disable','PGCONNECT_TIMEOUT':'15'},password
    except Exception:raise SafeStop('session_project_role_or_certificate_rejected') from None

@contextmanager
def runtime(uri,project,role,ca):
    config,password=fields(uri,project,role,ca)
    env={k:v for k,v in os.environ.items() if k.upper() in {'PATH','HOME','SYSTEMROOT','WINDIR','TEMP','TMP','COMSPEC','PATHEXT'}}
    env.update(config,LC_ALL='C')
    with tempfile.TemporaryDirectory(prefix='health-session-pass-') as name:
        directory=Path(name);directory.chmod(0o700);file=directory/'pgpass'
        def esc(s):return s.replace('\\','\\\\').replace(':','\\:')
        fd=os.open(file,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'w',encoding='utf-8') as f:f.write(':'.join(esc(config[k]) for k in ('PGHOST','PGPORT','PGDATABASE','PGUSER'))+':'+esc(password)+'\n')
        env['PGPASSFILE']=str(file);yield env

def probe(uri,project,role,ca):
    sql="BEGIN READ ONLY; SET LOCAL statement_timeout='15s'; SELECT jsonb_build_object('database',current_database(),'role',current_user,'session_user',session_user,'readonly',current_setting('transaction_read_only'),'primary',NOT pg_is_in_recovery(),'backend_tls',coalesce((SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()),false),'super',rolsuper,'bypass',rolbypassrls,'create_role',rolcreaterole,'create_db',rolcreatedb) FROM pg_roles WHERE rolname=current_user; COMMIT;"
    with runtime(uri,project,role,ca) as env:
        try:p=subprocess.run(['psql','-X','-q','-A','-t','-v','ON_ERROR_STOP=1','-c','\\conninfo','-c',sql],env=env,capture_output=True,text=True,encoding='utf-8',timeout=45)
        except Exception:raise SafeStop('session_probe_client_failed') from None
    if p.returncode:raise SafeStop('session_probe_connection_failed')
    try:
        identity=json.loads(p.stdout.strip().splitlines()[-1]);tls=re.search(r'TLSv1\.[23]',p.stdout)
        if not tls or identity['role']!=role or identity['session_user']!=role or identity['database']!='postgres' or identity['readonly']!='on' or not identity['primary']:raise ValueError()
        if role!='postgres' and any(identity[k] for k in ('super','create_role','create_db')):raise ValueError()
        if role in ('health_writer','health_test_ci') and identity['bypass']:raise ValueError()
    except Exception:raise SafeStop('session_probe_identity_tls_or_readonly_failed') from None
    return {'status':'ACTUAL_ACTIONS_SESSION_VERIFY_FULL_PASS','project_id':project,'identity':identity,'client_tls':tls[0],
     'sslmode':'verify-full','ca_sha256':CA_SHA,'workflow_sha':os.environ.get('GITHUB_SHA'),
     'run_id':os.environ.get('GITHUB_RUN_ID'),'run_attempt':os.environ.get('GITHUB_RUN_ATTEMPT'),
     'backend_tls_proven':identity['backend_tls'],'scope':'owner-approved client-to-Session-pooler boundary','clinical_writes':False}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--project',required=True,choices=POLICIES);p.add_argument('--role',required=True);p.add_argument('--ca',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    try:
        install_ca(a.ca)
        uri=os.environ.get('SUPABASE_DB_URL') or os.environ.get('HEALTH_TEST_WRITER_DB_URL','')
        result=probe(uri,a.project,a.role,a.ca.resolve())
    except SafeStop as e:result={'status':'STOPPED','safe_reason':str(e),'clinical_writes':False}
    except Exception:result={'status':'STOPPED','safe_reason':'probe_failed','clinical_writes':False}
    a.out.write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))
    if result['status']=='STOPPED':raise SystemExit(2)
