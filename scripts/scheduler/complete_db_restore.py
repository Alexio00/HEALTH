"""Actual isolated PG17 restore of private complete archives; no host ports.

Successful callers own the returned exact container context and must clean it
with cleanup(). Failed attempts remain stopped and private for diagnosis.
"""
import hashlib,json,re,secrets,subprocess,time,uuid
from pathlib import Path
from complete_sources import private
IMAGE='public.ecr.aws/supabase/postgres@sha256:06ddc7962e11ab0f4f0334fd05671e97c30ea202f6e6a7113800bd3d6e416108'
class RestoreStop(RuntimeError):pass

def restore_database(folder, attempt_folder):
    folder=private(folder);attempt_folder=private(attempt_folder,fresh=True)
    capture=json.loads((folder/'capture.private.json').read_text())
    name='health-complete-restore-'+uuid.uuid4().hex[:12]
    label='health.complete-restore='+name
    admin='health_recovery_'+uuid.uuid4().hex[:12]
    stage='input_validation';container=None
    def run(args,label,input=None,timeout=180):
        result=subprocess.run(args,input=input,capture_output=True,timeout=timeout)
        (attempt_folder/(label+'.restore.private.stderr')).write_bytes(result.stderr)
        (attempt_folder/(label+'.restore.private.stdout')).write_bytes(result.stdout)
        if result.returncode:raise RuntimeError('isolated_restore_failed:'+label)
        return result.stdout
    def sql(text,label,role=None):
        # Supabase's local socket uses peer mapping for the image administrator.
        # Connect as that identity, then SET ROLE to the disposable recovery superuser.
        if role is None:text='SET ROLE '+ident(admin)+';\n'+text
        return run(['docker','exec','-i',container,'psql','-XqAt','-U',role or 'supabase_admin','-d','postgres','-v','ON_ERROR_STOP=1'],label,text.encode()).decode().strip()
    def ident(value):return '"'+value.replace('"','""')+'"'
    def literal(value):return "'"+str(value).replace("'","''")+"'"
    try:
        if capture['status']!='ACTUAL_COHERENT_DB_AUTH_SNAPSHOT_CAPTURED_NOT_RESTORED':raise RuntimeError('uncaptured_input')
        for file,proof in capture['dumps'].items():
            if hashlib.sha256((folder/file).read_bytes()).hexdigest()!=proof['sha256']:raise RuntimeError('captured_dump_hash_mismatch')
        stage='start_platform'
        container=run(['docker','run','-d','--pull=never','--name',name,'--label',label,'--network=none','--mount','type=bind,source='+str(folder)+',target=/recovery,readonly','-e','POSTGRES_PASSWORD='+secrets.token_hex(24),'-e','JWT_SECRET='+secrets.token_hex(32),IMAGE],'start').decode().strip()
        if not re.fullmatch('[0-9a-f]{64}',container):raise RuntimeError('container_identity_invalid')
        ready=False
        for attempt in range(60):
            main=subprocess.run(['docker','exec',container,'cat','/proc/1/cmdline'],capture_output=True)
            executable=main.stdout.split(b'\0',1)[0].rsplit(b'/',1)[-1]
            if main.returncode or executable!=b'postgres':time.sleep(1);continue
            r=subprocess.run(['docker','exec',container,'pg_isready','-U','supabase_admin'],capture_output=True)
            if r.returncode==0:
                # pg_isready may see the temporary init server. Confirm platform migration finished.
                r=subprocess.run(['docker','exec',container,'psql','-XqAt','-U','supabase_admin','-d','postgres','-c',"SELECT to_regprocedure('auth.uid()') IS NOT NULL AND EXISTS(SELECT 1 FROM pg_roles WHERE rolname='authenticator');"],capture_output=True)
                if r.returncode==0 and r.stdout.strip()==b't':ready=True;break
            time.sleep(1)
        if not ready:raise RuntimeError('platform_start_timeout')
        sql('CREATE ROLE '+ident(admin)+' SUPERUSER LOGIN;','recovery_admin',role='supabase_admin')
        if int(sql('SHOW server_version_num;','server_version'))//10000!=17:raise RuntimeError('restore_platform_major_mismatch')
        stage='restore_role_catalog'
        roles=json.loads((folder/'roles.private.json').read_text())
        existing=set(json.loads(sql('SELECT jsonb_agg(rolname) FROM pg_roles;','existing_roles')))
        statements=[]
        for row in roles:
            # PostgreSQL built-in roles are reserved; verify their default attributes below.
            if row['rolname'].startswith('pg_'):continue
            n=ident(row['rolname'])
            if row['rolname'] not in existing:statements.append('CREATE ROLE '+n+';')
            attrs=['SUPERUSER' if row['rolsuper'] else 'NOSUPERUSER','INHERIT' if row['rolinherit'] else 'NOINHERIT','CREATEROLE' if row['rolcreaterole'] else 'NOCREATEROLE','CREATEDB' if row['rolcreatedb'] else 'NOCREATEDB','LOGIN' if row['rolcanlogin'] else 'NOLOGIN','REPLICATION' if row['rolreplication'] else 'NOREPLICATION','BYPASSRLS' if row['rolbypassrls'] else 'NOBYPASSRLS','CONNECTION LIMIT '+str(row['rolconnlimit'])]
            statements.append('ALTER ROLE '+n+' WITH '+' '.join(attrs)+' PASSWORD '+(literal(row['rolpassword']) if row['rolpassword'] else 'NULL')+' VALID UNTIL '+literal(row['rolvaliduntil'] or 'infinity')+';')
            statements.append('ALTER ROLE '+n+' RESET ALL;')
            for setting in row.get('rolconfig') or []:
                k,v=setting.split('=',1)
                if not re.fullmatch('[a-z_][a-z0-9_.]*',k):raise RuntimeError('unexpected_role_setting_name')
                statements.append('ALTER ROLE '+n+' SET '+k+' TO '+literal(v)+';')
        sql('\n'.join(statements),'restore_roles')
        null_expiry=[r['rolname'] for r in roles if r['rolvaliduntil'] is None and not r['rolname'].startswith('pg_')]
        sql('UPDATE pg_authid SET rolvaliduntil=NULL WHERE rolname IN ('+','.join(literal(n) for n in null_expiry)+');','restore_null_expiry')
        settings=json.loads((folder/'role-db-settings.private.json').read_text())
        settings_sql=['BEGIN; DELETE FROM pg_db_role_setting;']
        for entry in settings:
            db='0' if entry['database'] is None else '(SELECT oid FROM pg_database WHERE datname='+literal(entry['database'])+')'
            role='0' if entry['role'] is None else '(SELECT oid FROM pg_roles WHERE rolname='+literal(entry['role'])+')'
            values='ARRAY['+','.join(literal(v) for v in entry['settings'])+']::text[]'
            settings_sql.append('INSERT INTO pg_db_role_setting(setdatabase,setrole,setconfig) VALUES('+db+','+role+','+values+');')
        settings_sql.append('COMMIT;');sql('\n'.join(settings_sql),'restore_exact_db_role_settings')
        oid_to_name={r['oid']:r['rolname'] for r in roles}
        memberships=json.loads((folder/'role-memberships.private.json').read_text())
        statements=[]
        for row in memberships:
            statements.append('GRANT '+ident(oid_to_name[row['roleid']])+' TO '+ident(oid_to_name[row['member']])+' WITH ADMIN '+str(row['admin_option']).upper()+', INHERIT '+str(row['inherit_option']).upper()+', SET '+str(row['set_option']).upper()+' GRANTED BY '+ident(oid_to_name[row['grantor']])+';')
        sql('\n'.join(statements),'restore_memberships')
        stage='restore_database_archive'
        sql('DROP SCHEMA IF EXISTS public CASCADE; DROP SCHEMA IF EXISTS auth CASCADE; DROP SCHEMA IF EXISTS supabase_migrations CASCADE;','clear_isolated_schemas')
        run(['docker','exec',container,'pg_restore','-U','supabase_admin','--role='+admin,'-d','postgres','--exit-on-error','--single-transaction','/recovery/database.custom'],'archive_restore',timeout=600)
        stage='verify_fingerprints'
        for schema,key in [('public','clinical_fingerprints'),('auth','auth_fingerprints')]:
            parts=["SELECT "+literal(n)+" name,encode(sha256(convert_to(coalesce(string_agg(to_jsonb(t)::text,E'\\n' ORDER BY to_jsonb(t)::text),''),'UTF8')),'hex') digest FROM "+ident(schema)+'.'+ident(n)+' t' for n in capture[key]]
            actual=json.loads(sql('SELECT jsonb_object_agg(name,digest) FROM ('+' UNION ALL '.join(parts)+') q;','verify_'+schema))
            if actual!=capture[key]:raise RuntimeError('restored_'+schema+'_fingerprint_mismatch')
        all_parts=[]
        for full in capture['all_schema_table_fingerprints']:
            schema,table=full.split('.',1)
            all_parts.append('SELECT '+literal(full)+" name,encode(sha256(convert_to(coalesce(string_agg(to_jsonb(t)::text,E'\\n' ORDER BY to_jsonb(t)::text),''),'UTF8')),'hex') digest FROM "+ident(schema)+'.'+ident(table)+' t')
        all_actual=json.loads(sql('SELECT jsonb_object_agg(name,digest) FROM ('+' UNION ALL '.join(all_parts)+') q;','verify_all_tables'))
        if all_actual!=capture['all_schema_table_fingerprints']:raise RuntimeError('restored_all_table_fingerprint_mismatch')
        stage='verify_roles'
        restored=json.loads(sql('SELECT jsonb_agg(to_jsonb(r) ORDER BY rolname) FROM pg_authid r;','verify_roles'))
        by_name={r['rolname']:r for r in restored}
        keys=['rolname','rolsuper','rolinherit','rolcreaterole','rolcreatedb','rolcanlogin','rolreplication','rolbypassrls','rolconnlimit','rolpassword','rolvaliduntil']
        if any({k:r[k] for k in keys}!={k:by_name[r['rolname']][k] for k in keys} for r in roles):raise RuntimeError('restored_role_secret_or_attributes_mismatch')
        settings_actual=json.loads(sql("SELECT coalesce(jsonb_agg(jsonb_build_object('database',d.datname,'role',r.rolname,'settings',s.setconfig)),'[]'::jsonb) FROM pg_db_role_setting s LEFT JOIN pg_database d ON d.oid=s.setdatabase LEFT JOIN pg_roles r ON r.oid=s.setrole;",'verify_db_role_settings'))
        def ordered(entries):return sorted(entries,key=lambda x:(x['database'] or '',x['role'] or ''))
        if ordered(settings_actual)!=ordered(settings):raise RuntimeError('restored_db_role_settings_mismatch')
        memberships_actual=json.loads(sql("SELECT coalesce(jsonb_agg(jsonb_build_object('role',r.rolname,'member',m.rolname,'grantor',g.rolname,'admin_option',a.admin_option,'inherit_option',a.inherit_option,'set_option',a.set_option)),'[]'::jsonb) FROM pg_auth_members a JOIN pg_roles r ON r.oid=a.roleid JOIN pg_roles m ON m.oid=a.member JOIN pg_roles g ON g.oid=a.grantor;",'verify_role_memberships'))
        membership_count=verify_membership_binding(roles,memberships,memberships_actual)
        # Exact snapshot and role verification above precedes this deliberate
        # recovery safety change. Restoring a backup never activates Writer.
        writer_recovery=pause_restored_writer(sql)
        proof={'status':'ACTUAL_ISOLATED_SUPABASE_PG17_ALL_DB_AUTH_ROLE_SETTINGS_RESTORE_COMPONENT_PASS','clinical_tables_verified':len(capture['clinical_fingerprints']),'auth_tables_verified':len(capture['auth_fingerprints']),'all_dump_schema_tables_verified':len(all_actual),'role_catalog_password_hashes_and_attributes_restored_exactly':True,'role_db_settings_restored_exactly':True,'client_tls':'verify-full','source_corpus_verified':False,'auth_http_lifecycle':'NOT_RUN','full_replacement_backup_accepted':False,'production_writes':False,'published_ports':False,'container_network':'none','dump_sha256':capture['dumps']['database.custom']['sha256'],'platform_image':IMAGE}
        proof.update(role_memberships_restored_exactly=True,role_memberships_verified=membership_count)
        proof['writer_recovery']=writer_recovery
        (attempt_folder/'restore.private.json').write_text(json.dumps(proof,indent=2))
        (attempt_folder/'finish.private.json').write_text(json.dumps(proof,indent=2))
        return {'container':container,'name':name,'label':label,'private_folder':str(folder),'attempt_folder':str(attempt_folder),'proof':proof}
    except Exception as error:
        proof={'status':'STOPPED','stage':stage,'safe_reason':str(error) if isinstance(error,RuntimeError) else type(error).__name__,'production_writes':False}
        (attempt_folder/'restore-STOPPED.private.json').write_text(json.dumps(proof))
        if container:
            subprocess.run(['docker','stop','-t','10',container],capture_output=True)
        raise RestoreStop('isolated_database_restore_failed_'+stage) from None


def pause_restored_writer(sql):
    present=sql("SELECT to_regnamespace('health_writer') IS NOT NULL;",'writer_recovery_present')
    if present=='f':return {'writer_schema_present':False,'writer_automatically_resumed':False}
    if present!='t':raise RestoreStop('writer_recovery_schema_presence_unavailable')
    if sql("SELECT obj_description('health_writer'::regnamespace)='HEALTH_WRITER_STANDBY_V1';",'writer_recovery_identity')!='t':raise RestoreStop('writer_recovery_schema_identity_rejected')
    # Preserve all pending payloads, approvals, NNN reservations, audit rows and
    # resumable session URIs. Only runtime configuration is intentionally paused.
    names=json.loads(sql("SELECT coalesce(jsonb_agg(c.relname ORDER BY c.relname),'[]'::jsonb) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='health_writer' AND c.relkind='r' AND c.relname NOT IN ('runtime_policy','upload_folders');",'writer_pending_control_tables'))
    if not names or not all(re.fullmatch('[a-z_][a-z0-9_]*',n) for n in names):raise RestoreStop('writer_pending_control_catalog_rejected')
    parts=["SELECT '"+n+"' name,encode(sha256(convert_to(coalesce(string_agg(to_jsonb(x)::text,E'\\n' ORDER BY to_jsonb(x)::text),''),'UTF8')),'hex') digest FROM health_writer."+n+' x' for n in names]
    fps='SELECT jsonb_object_agg(name,digest) FROM ('+' UNION ALL '.join(parts)+') f;'
    before=sql(fps,'writer_pending_control_before_pause')
    prior=sql("SELECT enabled FROM health_writer.runtime_policy WHERE singleton;",'writer_prior_enabled')
    if prior not in ('t','f'):raise RestoreStop('writer_recovery_singleton_missing')
    sql("BEGIN; LOCK TABLE health_writer.runtime_policy,health_writer.upload_folders IN ACCESS EXCLUSIVE MODE; UPDATE health_writer.runtime_policy SET enabled=false,code_sha=NULL; UPDATE health_writer.upload_folders SET enabled=false; COMMIT;",'pause_restored_writer')
    if sql("SELECT count(*)=1 AND bool_and(NOT enabled AND code_sha IS NULL) AND NOT EXISTS(SELECT 1 FROM health_writer.upload_folders WHERE enabled) FROM health_writer.runtime_policy;",'writer_pause_readback')!='t':raise RestoreStop('writer_recovery_pause_readback_failed')
    if sql(fps,'writer_pending_control_after_pause')!=before:raise RestoreStop('writer_recovery_pending_control_changed')
    return {'writer_schema_present':True,'captured_writer_enabled':prior=='t','exact_snapshot_verified_before_pause':True,'restored_writer_enabled':False,'restored_code_pin_cleared':True,'all_upload_folders_disabled':True,'pending_journal_preserved':True,'pending_control_tables_verified':len(names),'writer_automatically_resumed':False,'new_source_root_and_separate_reacceptance_required':True}

def rebind_restored_writer(sql,new_root):
    if not re.fullmatch('[A-Za-z0-9_-]{8,128}',new_root):raise RestoreStop('writer_recovery_root_identity_rejected')
    present=sql("SELECT to_regnamespace('health_writer') IS NOT NULL;",'writer_rebind_present')
    if present=='f':return {'writer_schema_present':False,'writer_automatically_resumed':False}
    if present!='t' or sql("SELECT count(*)=1 AND bool_and(NOT enabled AND code_sha IS NULL) AND NOT EXISTS(SELECT 1 FROM health_writer.upload_folders WHERE enabled) FROM health_writer.runtime_policy;",'writer_rebind_disabled_guard')!='t':raise RestoreStop('writer_recovery_must_remain_paused')
    sql("BEGIN; UPDATE health_writer.runtime_policy SET primary_folder='"+new_root+"'; INSERT INTO health_writer.upload_folders VALUES('"+new_root+"',false) ON CONFLICT(folder) DO UPDATE SET enabled=false; COMMIT;",'writer_verified_new_root_rebind')
    if sql("SELECT primary_folder='"+new_root+"' AND NOT enabled AND code_sha IS NULL AND NOT EXISTS(SELECT 1 FROM health_writer.upload_folders WHERE enabled) FROM health_writer.runtime_policy WHERE singleton;",'writer_new_root_disabled_readback')!='t':raise RestoreStop('writer_recovery_new_root_readback_failed')
    return {'writer_schema_present':True,'verified_new_source_root_bound':True,'writer_remains_disabled':True,'old_pending_sessions_not_rebound_or_resumed':True,'writer_automatically_resumed':False}

def verify_membership_binding(roles,memberships,actual):
    names={r['oid']:r['rolname'] for r in roles}
    expected=[{'role':names[r['roleid']],'member':names[r['member']],'grantor':names[r['grantor']],
               **{k:r[k] for k in ('admin_option','inherit_option','set_option')}} for r in memberships]
    ordered=lambda entries:sorted(entries,key=lambda x:(x['role'],x['member'],x['grantor']))
    if ordered(expected)!=ordered(actual):raise RestoreStop('restored_role_membership_mismatch')
    return len(expected)

def cleanup(context):
    result=subprocess.run(['docker','inspect',context['container']],capture_output=True,timeout=30)
    if result.returncode:raise RestoreStop('isolated_cleanup_identity_unavailable')
    meta=json.loads(result.stdout)[0]
    folder=Path(context['private_folder']).resolve()
    if meta['Id']!=context['container'] or meta['Config']['Labels'].get('health.complete-restore')!=context['name'] or meta['HostConfig']['NetworkMode']!='none' or meta['HostConfig']['PortBindings'] or not any(Path(m['Source']).resolve()==folder and m['Destination']=='/recovery' and not m['RW'] for m in meta['Mounts']):
        raise RestoreStop('isolated_cleanup_boundary_rejected')
    logs=subprocess.run(['docker','logs',context['container']],capture_output=True,timeout=30)
    (Path(context['attempt_folder'])/'database.private.log').write_bytes(logs.stdout+logs.stderr)
    result=subprocess.run(['docker','rm','-f',context['container']],capture_output=True,timeout=60)
    if result.returncode:raise RestoreStop('isolated_cleanup_failed')
