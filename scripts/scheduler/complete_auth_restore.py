"""Actual Auth HTTP recovery in an isolated database network namespace.

Use fresh local credentials after exact catalog restoration proof. No original
owner password or previous signing secret is required. No production Auth calls.
"""
import base64,hashlib,hmac,json,secrets,subprocess,time,uuid,textwrap
from pathlib import Path
from complete_sources import private
from complete_db_restore import RestoreStop
PYTHON_IMAGE='python@sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258'

def restore_auth(context, stage):
    folder=private(context['private_folder']);attempt=private(context['attempt_folder'])
    stage=private(stage,fresh=True);name=context['name']
    auth_name='health-restored-auth-'+uuid.uuid4().hex[:12]
    auth=None;db=None;checks=[]
    def run(args,label,input=None,timeout=120):
        p=subprocess.run(args,input=input,capture_output=True,timeout=timeout)
        (stage/(label+'.private.stderr')).write_bytes(p.stderr)
        (stage/(label+'.private.stdout')).write_bytes(p.stdout)
        if p.returncode:raise RuntimeError('isolated_auth_failed:'+label)
        return p.stdout
    def sql(s,label):return run(['docker','exec','-i',db,'psql','-XqAt','-U','supabase_admin','-d','postgres','-v','ON_ERROR_STOP=1'],label,s.encode()).decode().strip()
    def check(name,ok):
        if not ok:raise RuntimeError('auth_check_failed:'+name)
        checks.append(name)
    def b64(raw):return base64.urlsafe_b64encode(raw).decode().rstrip('=')
    def request(method,path,body=None,token=None):
        payload=json.dumps({'method':method,'path':path,'body':body,'token':token}).encode()
        script="""
    import sys,json,urllib.request,urllib.error
    p=json.loads(sys.stdin.read());headers={'Content-Type':'application/json'}
    if p['token']:headers['Authorization']='Bearer '+p['token']
    req=urllib.request.Request('http://127.0.0.1:9999'+p['path'],data=json.dumps(p['body']).encode() if p['body'] is not None else None,headers=headers,method=p['method'])
    try:
     r=urllib.request.urlopen(req,timeout=20);print(json.dumps({'status':r.status,'body':json.loads(r.read() or '{}')}))
    except urllib.error.HTTPError as e:print(json.dumps({'status':e.code,'body':json.loads(e.read() or '{}')}))
    """
        return json.loads(run(['docker','run','-i','--rm','--pull=never','--network','container:'+db,'--read-only','--cap-drop=ALL','--security-opt=no-new-privileges',PYTHON_IMAGE,'python','-c',textwrap.dedent(script)],'http-'+str(len(checks)),payload))
    try:
        if json.loads((attempt/'finish.private.json').read_text())['status']!='ACTUAL_ISOLATED_SUPABASE_PG17_ALL_DB_AUTH_ROLE_SETTINGS_RESTORE_COMPONENT_PASS':raise RuntimeError('full_db_component_not_restored')
        meta=json.loads(run(['docker','inspect',name],'identity'))[0]
        if meta['Config']['Labels'].get('health.complete-restore')!=name or meta['HostConfig']['NetworkMode']!='none' or meta['HostConfig']['PortBindings']:raise RuntimeError('isolated_boundary_mismatch')
        db=meta['Id'];run(['docker','start',db],'start_db')
        db_ready=False
        for n in range(30):
            p=subprocess.run(['docker','exec',db,'pg_isready','-U','supabase_admin'],capture_output=True)
            if p.returncode==0:db_ready=True;break
            time.sleep(1)
        if not db_ready:raise RuntimeError('restored_db_start_timeout')
        password=secrets.token_hex(24);jwt_secret=secrets.token_hex(32)
        sql("ALTER ROLE supabase_auth_admin PASSWORD '"+password+"';",'local_auth_service_password')
        owner_ids=json.loads(sql("SELECT coalesce(jsonb_agg(id),'[]'::jsonb) FROM auth.users;",'restored_user_ids'))
        env={'GOTRUE_DB_DRIVER':'postgres','GOTRUE_DB_DATABASE_URL':('postgres'+'ql://supabase_auth_admin:')+password+'@127.0.0.1:5432/postgres?sslmode=disable','GOTRUE_API_HOST':'127.0.0.1','GOTRUE_API_PORT':'9999','GOTRUE_SITE_URL':'http://127.0.0.1:3000','API_EXTERNAL_URL':'http://127.0.0.1:9999','GOTRUE_JWT_SECRET':jwt_secret,'GOTRUE_JWT_ADMIN_ROLES':'service_role','GOTRUE_JWT_AUD':'authenticated','GOTRUE_JWT_DEFAULT_GROUP':'authenticated','GOTRUE_DISABLE_SIGNUP':'false','GOTRUE_MAILER_AUTOCONFIRM':'true'}
        args=['docker','run','-d','--pull=never','--name',auth_name,'--label','health.restored-auth='+auth_name,'--network','container:'+db]
        for k,v in env.items():args+=['-e',k+'='+v]
        args+=['public.ecr.aws/supabase/gotrue@sha256:1736a63078f5922b198c4cbe50f80ab9a2d3b54fe8b7b6cfb2e9dc5dbbc12c6b']
        auth=run(args,'start_auth').decode().strip()
        ready=False
        for n in range(40):
            p=subprocess.run(['docker','exec',auth,'wget','-q','-O','-','http://127.0.0.1:9999/health'],capture_output=True)
            if p.returncode==0:ready=True;break
            time.sleep(1)
        check('restored_auth_service_healthy',ready)
        # Auth startup must preserve all captured tables before synthetic lifecycle writes.
        capture=json.loads((folder/'capture.private.json').read_text())
        parts=["SELECT '"+n+"' name,encode(sha256(convert_to(coalesce(string_agg(to_jsonb(t)::text,E'\\n' ORDER BY to_jsonb(t)::text),''),'UTF8')),'hex') digest FROM auth."+n+' t' for n in capture['auth_fingerprints']]
        fps=json.loads(sql('SELECT jsonb_object_agg(name,digest) FROM ('+' UNION ALL '.join(parts)+') q;','post_auth_start_fingerprints'))
        check('all_27_auth_table_fingerprints_preserved_on_service_start',fps==capture['auth_fingerprints'])
        now=int(time.time());unsigned=b64(json.dumps({'alg':'HS256','typ':'JWT'}).encode())+'.'+b64(json.dumps({'role':'service_role','aud':'authenticated','iss':'supabase','iat':now,'exp':now+1800}).encode())
        service=unsigned+'.'+b64(hmac.new(jwt_secret.encode(),unsigned.encode(),hashlib.sha256).digest())
        for index,user_id in enumerate(owner_ids):
            result=request('GET','/admin/users/'+user_id,token=service)
            check('restored_user_admin_http_read_'+str(index),result['status']==200 and result['body']['id']==user_id)
        email='restore-'+uuid.uuid4().hex+'@example.invalid';user_password=secrets.token_hex(24)
        created=request('POST','/admin/users',{'email':email,'password':user_password,'email_confirm':True},service)
        check('synthetic_user_created_by_actual_auth_http',created['status'] in (200,201) and bool(created['body'].get('id')))
        uid=created['body']['id']
        login=request('POST','/token?grant_type=password',{'email':email,'password':user_password})
        check('actual_password_login',login['status']==200 and login['body']['user']['id']==uid and bool(login['body'].get('refresh_token')))
        refresh=request('POST','/token?grant_type=refresh_token',{'refresh_token':login['body']['refresh_token']})
        check('actual_refresh_session',refresh['status']==200 and refresh['body']['user']['id']==uid)
        deleted=request('DELETE','/admin/users/'+uid,token=service)
        check('synthetic_user_deleted_locally',deleted['status'] in (200,204))
        denied=request('POST','/token?grant_type=password',{'email':email,'password':user_password})
        check('deleted_user_cannot_login',denied['status'] in (400,401))
        proof={'status':'ACTUAL_RESTORED_AUTH_HTTP_COMPONENT_PASS','checks':checks,'restored_user_count_verified_via_auth_http':len(owner_ids),'original_owner_password_login':'NOT_RUN_NO_PASSWORD_REQUIRED','original_27_auth_tables_preserved_at_service_start':True,'synthetic_lifecycle_only':True,'local_auth_db_password_replaced_after_exact_role_restore_proof':True,'production_writes':False,'published_ports':False,'container_network':'shared network-none namespace','full_replacement_backup_accepted':False,'dump_sha256':capture['dumps']['database.custom']['sha256']}
        (stage/'proof.private.json').write_text(json.dumps(proof,indent=2))
        return proof
    except Exception as e:
        proof={'status':'STOPPED','safe_reason':str(e) if isinstance(e,RuntimeError) else type(e).__name__,'checks_completed':checks,'production_writes':False}
        (stage/'STOPPED.private.json').write_text(json.dumps(proof))
        raise RestoreStop('isolated_auth_http_restore_failed') from None
    finally:
        if auth:
            meta_result=subprocess.run(['docker','inspect',auth],capture_output=True,timeout=30)
            if meta_result.returncode:raise RestoreStop('auth_cleanup_identity_unavailable')
            meta=json.loads(meta_result.stdout)[0]
            if meta['Id']!=auth or meta['Config']['Labels'].get('health.restored-auth')!=auth_name or meta['HostConfig']['NetworkMode']!='container:'+context['container'] or meta['HostConfig']['PortBindings']:
                raise RestoreStop('auth_cleanup_boundary_rejected')
            logs=subprocess.run(['docker','logs',auth],capture_output=True,timeout=30)
            (stage/'auth.private.log').write_bytes(logs.stdout+logs.stderr)
            result=subprocess.run(['docker','rm','-f',auth],capture_output=True,timeout=60)
            if result.returncode:raise RestoreStop('auth_cleanup_failed')
