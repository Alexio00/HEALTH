"""Coherent complete DB/Auth capture; no remote upload, rotation or activation.

Inputs: SUPABASE_DB_URL, HEALTH_SUPABASE_CA_PEM,
HEALTH_COMPLETE_PRIVATE_ROOT (fresh protected runtime directory).
Output locators and all payload remain in that private directory.
"""
from queue import Queue,Empty
import datetime,hashlib,json,os,re,subprocess,sys,uuid,threading
from pathlib import Path
from urllib.parse import urlsplit,unquote
from session_pooler_tls import install_ca,fields
ROOT=Path(os.environ['HEALTH_COMPLETE_PRIVATE_ROOT']).resolve()
if ROOT.is_symlink() or not ROOT.is_dir() or any(ROOT.iterdir()):raise RuntimeError('fresh_private_capture_root_required')
if os.name!='nt' and ROOT.stat().st_mode&0o077:raise RuntimeError('private_capture_root_permissions_required')
IMAGE='postgres@sha256:2d2b8998d31037bf721cfdf764d76ba74171b4fab3431b7f72c27c56ddbdf9e3'
TABLES=['domains','analytes','records','record_domains','sources','source_locations','record_sources','cases','case_links','labs','medications','monitoring','plan_items','questions','id_reservations']
folder=ROOT/('complete-snapshot-'+uuid.uuid4().hex[:12]);folder.mkdir(mode=0o700)
if os.name=='nt':
 sid=re.search(r'S-1-5-[0-9-]+',subprocess.check_output(['whoami','/user','/fo','csv','/nh'],text=True))[0]
 if subprocess.run(['icacls',str(folder),'/inheritance:r','/grant:r','*'+sid+':(OI)(CI)F'],capture_output=True).returncode:raise RuntimeError('private_acl_failed')
p=urlsplit(os.environ['SUPABASE_DB_URL'])
role=unquote(p.username or '').split('.',1)[0]
if role not in ('postgres','health_backup_reader'):raise RuntimeError('approved_capture_reader_identity_required')
if os.environ.get('HEALTH_REQUIRE_RESTRICTED_CAPTURE')=='1' and role!='health_backup_reader':raise RuntimeError('restricted_capture_principal_required')
inputs=folder/'transport';inputs.mkdir(mode=0o700)
install_ca(inputs/'ca.pem')
fields(os.environ['SUPABASE_DB_URL'],'ffvqgbslvjocbwfurxrv',role,(inputs/'ca.pem').resolve())

def esc(s):return s.replace('\\','\\\\').replace(':','\\:')
(inputs/'pgpass').write_text(':'.join(esc(s) for s in (p.hostname,'5432','postgres',unquote(p.username),unquote(p.password)))+'\n')
uid,gid=(65532,65532) if os.name=='nt' else (os.getuid(),os.getgid())
base=['docker','run','-i','--rm','--pull=never','--read-only','--user',str(uid)+':'+str(gid),'--cap-drop=ALL','--security-opt=no-new-privileges',
 '--tmpfs',f'/private:rw,noexec,nosuid,nodev,mode=0700,uid={uid},gid={gid}','--mount','type=bind,source='+str(inputs)+',target=/run/input,readonly',
 '-e','PGHOST='+p.hostname,'-e','PGPORT=5432','-e','PGUSER='+unquote(p.username),'-e','PGDATABASE=postgres',
 '-e','PGSSLMODE=verify-full','-e','PGSSLROOTCERT=/run/input/ca.pem','-e','PGGSSENCMODE=disable','-e','PGPASSFILE=/private/pgpass','-e','PGCONNECT_TIMEOUT=15','-e','PGOPTIONS=-c default_transaction_read_only=on','--entrypoint','sh',IMAGE,
 '-c','cp /run/input/pgpass /private/pgpass && chmod 600 /private/pgpass && exec "$@"','health-private']
controller=None; heartbeat=None; heartbeat_stop=threading.Event(); heartbeat_errors=[]; controller_lock=threading.Lock();lines=Queue()
def command(tool,*args):return base+[tool,*args]
def query(sql,label):
 r=subprocess.run(command('psql','-X','-q','-A','-t','-v','ON_ERROR_STOP=1'),input=sql.encode(),capture_output=True,timeout=60)
 (folder/(label+'.private.stderr')).write_bytes(r.stderr)
 if r.returncode:raise RuntimeError('private_readonly_query_failed:'+label)
 return r.stdout
def controller_query(sql):
 with controller_lock:
  controller.stdin.write(sql+'\n');controller.stdin.flush()
  try:
   line=lines.get(timeout=30)
   if line is None:raise RuntimeError('snapshot_controller_closed')
   return line.strip()
  except Empty:raise RuntimeError('snapshot_controller_deadline_exceeded') from None
try:
 controller=subprocess.Popen(command('psql','-X','-q','-A','-t','-v','ON_ERROR_STOP=1'),stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=(folder/'snapshot-controller.private.stderr').open('w'),text=True,encoding='utf-8')
 def read_controller():
  for line in controller.stdout:lines.put(line)
  lines.put(None)
 threading.Thread(target=read_controller,daemon=True).start()
 snap=controller_query('BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY; SET LOCAL statement_timeout=\'30min\'; SET LOCAL idle_in_transaction_session_timeout=\'15min\'; SELECT pg_export_snapshot();')
 if not re.fullmatch(r'[0-9A-F]+-[0-9A-F]+-[0-9]+',snap):raise RuntimeError('exported_snapshot_invalid')
 version=controller_query('SHOW server_version_num;')
 if int(version)//10000!=17:raise RuntimeError('server_client_major_mismatch')
 if role=='health_backup_reader':
  capability=json.loads(controller_query("SELECT jsonb_build_object('principal',session_user,'super',rolsuper,'create_role',rolcreaterole,'create_db',rolcreatedb,'inherit',rolinherit,'bypass',rolbypassrls,'owned_tables',(SELECT count(*) FROM pg_class WHERE relowner=(SELECT oid FROM pg_roles WHERE rolname=session_user) AND relkind IN ('r','p','S')),'table_dml',(SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname NOT IN ('pg_catalog','information_schema') AND c.relkind IN ('r','p') AND (has_table_privilege(session_user,c.oid,'INSERT') OR has_table_privilege(session_user,c.oid,'UPDATE') OR has_table_privilege(session_user,c.oid,'DELETE') OR has_table_privilege(session_user,c.oid,'TRUNCATE'))),'other_privileged_execute',(SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname NOT IN ('pg_catalog','information_schema') AND has_schema_privilege(session_user,n.oid,'USAGE') AND p.prosecdef AND has_function_privilege(session_user,p.oid,'EXECUTE') AND NOT (n.nspname='health_backup_control' AND p.proname='export_role_catalog' AND p.pronargs=0)),'read_all_membership',(SELECT count(*) FROM pg_auth_members WHERE member=(SELECT oid FROM pg_roles WHERE rolname=session_user) AND roleid='pg_read_all_data'::regrole AND inherit_option AND NOT admin_option AND NOT set_option),'other_memberships',(SELECT count(*) FROM pg_auth_members WHERE member=(SELECT oid FROM pg_roles WHERE rolname=session_user) AND roleid<>'pg_read_all_data'::regrole),'direct_role_secrets',has_table_privilege(session_user,'pg_authid','SELECT')) FROM pg_roles WHERE rolname=session_user;"))
  if capability['principal']!='health_backup_reader' or capability['read_all_membership']!=1 or not capability['direct_role_secrets'] or not capability['bypass'] or any(capability[k] for k in ('super','create_role','create_db','inherit','owned_tables','table_dml','other_privileged_execute','other_memberships')):
   raise RuntimeError('complete_reader_privileges_outside_fixed_capability')
 parts=["SELECT '"+name+"' AS name,encode(sha256(convert_to(coalesce(string_agg(to_jsonb(t)::text,E'\\n' ORDER BY to_jsonb(t)::text),''),'UTF8')),'hex') AS digest FROM public."+name+' t' for name in TABLES]
 fps=json.loads(controller_query('SELECT jsonb_object_agg(name,digest) FROM ('+' UNION ALL '.join(parts)+') fingerprints;'))
 auth_tables=json.loads(controller_query("SELECT jsonb_agg(c.relname ORDER BY c.relname) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='auth' AND c.relkind IN ('r','p');"))
 auth_parts=["SELECT '"+name+"' AS name,encode(sha256(convert_to(coalesce(string_agg(to_jsonb(t)::text,E'\\n' ORDER BY to_jsonb(t)::text),''),'UTF8')),'hex') AS digest FROM auth."+name+' t' for name in auth_tables if re.fullmatch('[a-z_][a-z0-9_]*',name)]
 auth_fps=json.loads(controller_query('SELECT jsonb_object_agg(name,digest) FROM ('+' UNION ALL '.join(auth_parts)+') fingerprints;'))
 roles=controller_query('SELECT health_backup_control.export_role_catalog();' if role=='health_backup_reader' else 'SELECT jsonb_agg(to_jsonb(r) ORDER BY rolname) FROM pg_authid r;')
 (folder/'roles.private.json').write_text(roles,encoding='utf-8')
 members=controller_query('SELECT coalesce(jsonb_agg(to_jsonb(r)),\'[]\'::jsonb) FROM pg_auth_members r;')
 (folder/'role-memberships.private.json').write_text(members,encoding='utf-8')
 settings=controller_query("SELECT coalesce(jsonb_agg(jsonb_build_object('database',d.datname,'role',r.rolname,'settings',s.setconfig) ORDER BY s.setdatabase,s.setrole),'[]'::jsonb) FROM pg_db_role_setting s LEFT JOIN pg_database d ON d.oid=s.setdatabase LEFT JOIN pg_roles r ON r.oid=s.setrole;")
 (folder/'role-db-settings.private.json').write_text(settings,encoding='utf-8')
 all_tables=json.loads(controller_query("SELECT jsonb_agg(jsonb_build_object('schema',n.nspname,'table',c.relname) ORDER BY n.nspname,c.relname) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname IN ('public','auth','supabase_migrations','health_writer','health_backup_control') AND c.relkind IN ('r','p');"))
 all_parts=[]
 for item in all_tables:
  schema,name=item['schema'],item['table']
  if not re.fullmatch('[a-z_][a-z0-9_]*',schema) or not re.fullmatch('[a-z_][a-z0-9_]*',name):raise RuntimeError('unexpected_dump_table_identifier')
  all_parts.append("SELECT '"+schema+'.'+name+"' AS name,encode(sha256(convert_to(coalesce(string_agg(to_jsonb(t)::text,E'\\n' ORDER BY to_jsonb(t)::text),''),'UTF8')),'hex') AS digest FROM "+schema+'.'+name+' t')
 all_fps=json.loads(controller_query('SELECT jsonb_object_agg(name,digest) FROM ('+' UNION ALL '.join(all_parts)+') fingerprints;'))
 graph=controller_query("SELECT jsonb_build_object('sources',(SELECT coalesce(jsonb_agg(to_jsonb(s)),'[]'::jsonb) FROM public.sources s),'locations',(SELECT coalesce(jsonb_agg(to_jsonb(l)),'[]'::jsonb) FROM public.source_locations l));")
 (folder/'source-graph.private.json').write_text(graph,encoding='utf-8')
 (folder/'checkpoint.private.json').write_text(json.dumps({'snapshot':snap,'clinical_fingerprints':fps,'auth_fingerprints':auth_fps,'all_schema_table_fingerprints':all_fps,'roles_sha256':hashlib.sha256(roles.encode()).hexdigest(),'role_db_settings_sha256':hashlib.sha256(settings.encode()).hexdigest()},indent=2))
 def keepalive():
  while not heartbeat_stop.wait(10):
   try:
    if controller_query('SELECT 1;')!='1':raise RuntimeError('snapshot_keepalive_failed')
   except Exception:heartbeat_errors.append('snapshot_keepalive_failed');return
 heartbeat=threading.Thread(target=keepalive,daemon=True);heartbeat.start()
 checks={}
 for name,flags in [('database.custom',['--format=custom']),('schema.sql',['--schema-only']),('data.sql',['--data-only'])]:
  file=folder/name
  with file.open('wb') as out,(folder/(name+'.private.stderr')).open('wb') as err:
   r=subprocess.run(command('pg_dump','--snapshot='+snap,'--schema=public','--schema=auth','--schema=supabase_migrations','--schema=health_writer','--schema=health_backup_control',*flags),stdout=out,stderr=err,timeout=600)
  if r.returncode:raise RuntimeError('private_pg_dump_failed:'+name)
  if file.stat().st_size==0:raise RuntimeError('empty_dump:'+name)
  checks[name]={'sha256':hashlib.sha256(file.read_bytes()).hexdigest(),'bytes':file.stat().st_size}
  if heartbeat_errors:raise RuntimeError('snapshot_keepalive_failed')
 heartbeat_stop.set();heartbeat.join(timeout=35)
 if heartbeat.is_alive() or heartbeat_errors:raise RuntimeError('snapshot_keepalive_shutdown_failed')
 controller.stdin.write('ROLLBACK;\n\\q\n');controller.stdin.flush();controller.communicate(timeout=30)
 if controller.returncode:raise RuntimeError('exporter_close_failed')
 evidence={'status':'ACTUAL_COHERENT_DB_AUTH_SNAPSHOT_CAPTURED_NOT_RESTORED','exported_snapshot':snap,'clinical_fingerprints':fps,'auth_fingerprints':auth_fps,'all_schema_table_fingerprints':all_fps,'roles_sha256':hashlib.sha256(roles.encode()).hexdigest(),'role_db_settings_sha256':hashlib.sha256(settings.encode()).hexdigest(),'dumps':checks,'client_image':IMAGE,'client_tls':'verify-full','capture_role':role,'restricted_role_enforced':role=='health_backup_reader','clinical_writes':False,'source_corpus_captured':False,'full_replacement_backup_accepted':False}
 (folder/'capture.private.json').write_text(json.dumps(evidence,indent=2))
 (ROOT/'capture-locator.private.json').write_text(json.dumps({'private_folder':str(folder),'status':evidence['status']}))
 print(json.dumps({'status':evidence['status'],'clinical_tables':len(fps),'auth_tables':len(auth_fps),'dump_count':len(checks),'clinical_writes':False,'remote_uploads':False}))
except Exception as e:
 (folder/'STOPPED.private.json').write_text(json.dumps({'status':'STOPPED','safe_reason':str(e) if isinstance(e,RuntimeError) else type(e).__name__}))
 (ROOT/'capture-locator.private.json').write_text(json.dumps({'private_folder':str(folder),'status':'STOPPED','safe_reason':str(e) if isinstance(e,RuntimeError) else type(e).__name__}))
 print(json.dumps({'status':'STOPPED','safe_reason':str(e) if isinstance(e,RuntimeError) else type(e).__name__,'clinical_writes':False}));raise SystemExit(2)
finally:
 heartbeat_stop.set()
 if heartbeat:heartbeat.join(timeout=35)
 if controller and controller.poll() is None:
  try:controller.stdin.write('ROLLBACK;\n\\q\n');controller.stdin.flush();controller.communicate(timeout=30)
  except Exception:controller.terminate()
 for file in inputs.iterdir():file.unlink()
 inputs.rmdir()
