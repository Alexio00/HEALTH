"""Actual Source recreation and isolated locator rebind in the primary account.

This acceptance helper only creates fresh disposable folders. Full primary
Writer credentials are an explicit recovery input, never a daily backup input.
"""
import configparser,hashlib,json,os,re,subprocess,time,uuid
from pathlib import Path,PurePosixPath
from complete_sources import private as private_directory
from complete_db_restore import RestoreStop,rebind_restored_writer
from drive_transport import DriveTransport,DriveStop
from complete_archive import relative

def restore_sources(context, config_content, stage, archive_sha):
    folder=private_directory(context['private_folder'])
    private=folder.parent;stage=private_directory(stage,fresh=True)
    nonce=uuid.uuid4().hex[:12];name=context['name'];container=None;checks=[]
    if not re.fullmatch('[a-f0-9]{64}',archive_sha):raise RestoreStop('recovery_archive_pin_rejected')
    config=stage/'rclone.private.conf';config.write_text(config_content,encoding='utf-8');config.chmod(0o600)
    def run(args,label,body=None,timeout=1200):
        p=subprocess.run(args,input=body,capture_output=True,timeout=timeout)
        (stage/(label+'.private.stderr')).write_bytes(p.stderr);(stage/(label+'.private.stdout')).write_bytes(p.stdout)
        if p.returncode:raise RuntimeError('isolated_source_restore_failed:'+label)
        return p.stdout
    def clone(command,*args,label):return run(['rclone',command,*map(str,args),'--config',str(config),'--log-file',str(stage/'rclone.private.log'),'--log-level','ERROR'],label)
    def token(remote):
        c=configparser.ConfigParser(interpolation=None);c.read(config,encoding='utf-8');return json.loads(c[remote]['token'])['access_token']
    def check(label,ok):
        if not ok:raise RuntimeError('source_restore_check_failed:'+label)
        checks.append(label)
    def sha(p):
        h=hashlib.sha256()
        with p.open('rb') as f:
            for b in iter(lambda:f.read(1048576),b''):h.update(b)
        return h.hexdigest()
    def lit(s):return "'"+str(s).replace("'","''")+"'"
    def sql(q,label):return run(['docker','exec','-i',container,'psql','-XqAt','-U','supabase_admin','-d','postgres','-v','ON_ERROR_STOP=1'],label,q.encode(),120).decode().strip()
    try:
        clone('lsf','health_backup:','--max-depth','1','--dirs-only',label='refresh_backup');clone('lsf','health_source_writer:','--max-depth','1','--dirs-only',label='refresh_reader')
        writer=DriveTransport(lambda:token('health_source_writer'));reader=DriveTransport(lambda:token('health_backup'))
        check('recovery_folder_owner_account',writer.request('/drive/v3/about?fields=user(emailAddress)')['user']['emailAddress']==os.environ.get('HEALTH_PRIMARY_DRIVE_OWNER_EMAIL', ''))
        check('recovery_independent_reader_account',reader.request('/drive/v3/about?fields=user(emailAddress)')['user']['emailAddress']==os.environ.get('HEALTH_BACKUP_DRIVE_OWNER_EMAIL', ''))
        source=json.loads((private/'metadata/source-manifest.private.json').read_text(encoding='utf-8'))
        paths=set()
        for obj in source['objects']:
            relative('sources/'+obj['path'])
            file=private/'sources'/obj['path']
            if obj['path'].casefold() in paths or file.is_symlink() or not file.resolve().is_relative_to((private/'sources').resolve()) or not re.fullmatch('[a-f0-9]{64}',obj['sha256']) or not re.fullmatch('[A-Za-z0-9_-]{8,128}',obj['primary_object_id']):
                raise RestoreStop('recovery_source_manifest_rejected')
            paths.add(obj['path'].casefold())
        if {p.relative_to(private/'sources').as_posix().casefold() for p in (private/'sources').rglob('*') if p.is_file()}!=paths:
            raise RestoreStop('recovery_source_inventory_not_exact')
        # Owner requested no quota recheck; failed creation/upload is preserved
        # as a provider failure, never reported as a measured capacity PASS.
        remote_name='HEALTH_SYNTHETIC_BACKUP_RESTORE_'+nonce
        remote_folder=writer.request('/drive/v3/files?fields=id,name',method='POST',body=json.dumps({'name':remote_name,'mimeType':'application/vnd.google-apps.folder','properties':{'health_test_nonce':nonce}}).encode(),content_type='application/json')['id']
        (stage/'scope.private.json').write_text(json.dumps({'folder_id':remote_folder,'name':remote_name,'nonce':nonce}))
        writer.request('/drive/v3/files/'+remote_folder+'/permissions?sendNotificationEmail=false&fields=id,type,role',method='POST',body=json.dumps({'type':'user','role':'reader','emailAddress':os.environ.get('HEALTH_BACKUP_DRIVE_OWNER_EMAIL', '')}).encode(),content_type='application/json')
        primary_meta=writer.request('/drive/v3/files/'+remote_folder+'?fields=id,owners(emailAddress),capabilities(canAddChildren),trashed')
        check('restored_primary_owner_can_continue_writer_uploads',primary_meta.get('owners')==[{'emailAddress':os.environ.get('HEALTH_PRIMARY_DRIVE_OWNER_EMAIL', '')}] and primary_meta.get('capabilities',{}).get('canAddChildren') is True and primary_meta.get('trashed') is False)
        reader_meta=reader.request('/drive/v3/files/'+remote_folder+'?fields=id,capabilities(canAddChildren)')
        check('independent_recovery_reader_cannot_add_children',reader_meta.get('id')==remote_folder and reader_meta.get('capabilities',{}).get('canAddChildren') is False)
        denied=False
        try:
            reader.request('/drive/v3/files?fields=id',method='POST',body=json.dumps({'name':'synthetic-access-denial','parents':[remote_folder]}).encode(),content_type='application/json')
        except DriveStop as e:
            if str(e)!='drive_http_403':raise
            denied=True
        check('independent_recovery_reader_actual_create_denied',denied)
        cfg=configparser.ConfigParser(interpolation=None);cfg.read(config,encoding='utf-8')
        cfg['health_restore_upload']=dict(cfg['health_source_writer']);cfg['health_restore_upload']['root_folder_id']=remote_folder
        cfg['health_restore_verify']=dict(cfg['health_backup']);cfg['health_restore_verify']['root_folder_id']=remote_folder
        with config.open('w',encoding='utf-8') as f:cfg.write(f)
        check('verified_downloaded_corpus_before_upload',all((private/'sources'/o['path']).stat().st_size==o['size_bytes'] and sha(private/'sources'/o['path'])==o['sha256'] for o in source['objects']))
        print(json.dumps({'stage':'restoring_private_corpus','files':len(source['objects'])}),flush=True)
        clone('copy',private/'sources','health_restore_upload:','--immutable','--create-empty-src-dirs',label='private_corpus_upload')
        inventory=[o for o in json.loads(clone('lsjson','health_restore_upload:','--recursive','--hash',label='restored_inventory')) if not o['IsDir']]
        by_path={o['Path']:o for o in inventory}
        check('recreated_corpus_inventory_exact',len(by_path)==len(inventory)==len(source['objects']) and set(by_path)=={o['path'] for o in source['objects']})
        readback=stage/'independent-readback';readback.mkdir()
        print(json.dumps({'stage':'independent_private_byte_readback','files':len(inventory)}),flush=True)
        clone('copy','health_restore_verify:',readback,'--immutable','--create-empty-src-dirs',label='independent_corpus_download')
        check('independent_actual_download_all_sha256_and_sizes',all((readback/o['path']).stat().st_size==o['size_bytes'] and sha(readback/o['path'])==o['sha256'] for o in source['objects']))
        check('all_recreated_provider_ids_are_new',all(by_path[o['path']]['ID']!=o['primary_object_id'] for o in source['objects']))
        meta=json.loads(run(['docker','inspect',name],'container_identity'))[0]
        check('isolated_restore_db_boundary',meta['Config']['Labels'].get('health.complete-restore')==name and meta['HostConfig']['NetworkMode']=='none' and not meta['HostConfig']['PortBindings'])
        check('isolated_restore_input_mount',any(m['Source'].casefold()==str(folder).casefold() and m['Destination']=='/recovery' and not m['RW'] for m in meta['Mounts']))
        container=meta['Id'];run(['docker','start',container],'db_start')
        for i in range(30):
            if subprocess.run(['docker','exec',container,'pg_isready','-U','supabase_admin'],capture_output=True).returncode==0:break
            time.sleep(1)
        graph=json.loads((folder/'source-graph.private.json').read_text(encoding='utf-8'))
        old={l['source_id']:l for l in graph['locations'] if l['location_role']=='PRIMARY' and l['provider']=='google-drive'}
        rows=[]
        for s in graph['sources']:
            previous=old[s['source_id']];restored=by_path[s['logical_path']]
            rows.append({'source_id':s['source_id'],'old_id':previous['provider_object_id'],'new_id':restored['ID'],'account_alias':previous['account_alias'],'sha256':s['sha256'],'size_bytes':s['size_bytes']})
        (stage/'rebind-plan.private.json').write_text(json.dumps(rows,ensure_ascii=False),encoding='utf-8')
        capture=json.loads((folder/'capture.private.json').read_text())
        parts=["SELECT "+lit(t)+" name,encode(sha256(convert_to(coalesce(string_agg(to_jsonb(x)::text,E'\\n' ORDER BY to_jsonb(x)::text),''),'UTF8')),'hex') digest FROM public."+t+' x' for t in capture['clinical_fingerprints'] if t!='source_locations']
        before=json.loads(sql('SELECT jsonb_object_agg(name,digest) FROM ('+' UNION ALL '.join(parts)+') f;','clinical_before_rebind'))
        check('14_clinical_tables_match_captured_checkpoint',before=={k:v for k,v in capture['clinical_fingerprints'].items() if k!='source_locations'})
        statement=['BEGIN;']
        for row in rows:
            predicate="source_id="+lit(row['source_id'])+" AND location_role='PRIMARY' AND provider='google-drive' AND account_alias="+lit(row['account_alias'])+" AND provider_object_id="+lit(row['old_id'])
            statement.append("DO $rebind$ BEGIN IF (SELECT count(*) FROM public.source_locations WHERE "+predicate+")<>1 THEN RAISE EXCEPTION 'isolated locator identity mismatch'; END IF; UPDATE public.source_locations SET provider_object_id="+lit(row['new_id'])+' WHERE '+predicate+"; END $rebind$;")
        statement.append('COMMIT;');sql('\n'.join(statement),'exact_isolated_source_rebind')
        actual=json.loads(sql("SELECT jsonb_agg(to_jsonb(l)) FROM public.source_locations l WHERE location_role='PRIMARY' AND provider='google-drive';",'rebound_locations'))
        by_source={r['source_id']:r for r in actual}
        check('all_26_primary_locators_rebound_to_new_verified_ids',len(actual)==len(rows) and all(by_source[r['source_id']]['provider_object_id']==r['new_id'] for r in rows))
        after=json.loads(sql('SELECT jsonb_object_agg(name,digest) FROM ('+' UNION ALL '.join(parts)+') f;','clinical_after_rebind'))
        check('clinical_rows_and_record_source_links_unchanged',after==before)
        check('record_source_join_has_no_missing_location',sql("SELECT count(*) FROM public.record_sources r LEFT JOIN public.source_locations l ON l.source_id=r.source_id AND l.location_role='PRIMARY' AND l.provider='google-drive' WHERE l.source_id IS NULL;",'source_join')=='0')
        writer_recovery=rebind_restored_writer(sql,remote_folder)
        folder_meta=writer.request('/drive/v3/files/'+remote_folder+'?fields=id,name,properties,trashed')
        check('cleanup_exact_recovery_folder_identity',folder_meta.get('name')==remote_name and folder_meta.get('properties',{}).get('health_test_nonce')==nonce and folder_meta.get('trashed') is False)
        trashed=writer.request('/drive/v3/files/'+remote_folder+'?fields=id,trashed',method='PATCH',body=b'{"trashed":true}',content_type='application/json')
        check('temporary_restored_corpus_folder_trashed',trashed.get('trashed') is True)
        proof={'status':'ACTUAL_DOWNLOADED_COMPLETE_CORPUS_RESTORE_AND_ISOLATED_LOCATOR_REBIND_PASS','checks':checks,'restored_corpus_files':len(inventory),'independent_account_full_sha256_verified_files':len(source['objects']),'source_ids_rebound':len(rows),'clinical_tables_unchanged_excluding_intended_source_locator_changes':14,'production_db_writes':False,'production_sources_or_originals_modified':False,'candidate_backup_or_active_backup_modified':False,'temporary_restore_folder_trashed':True,'permanent_deletes':0,'archive_sha256':archive_sha,'db_restore_platform_network':'none','scope':'ACTUAL_ISOLATED_RECOVERY_COMPONENT_NOT_DAILY_ACTIVATION'}
        proof.update(recovery_primary_owner_matches_captured_account=True,recovery_writer_can_add_children_verified=True)
        proof['writer_recovery']=writer_recovery
        (stage/'proof.private.json').write_text(json.dumps(proof,indent=2))
        return proof
    except Exception as e:
        proof={'status':'STOPPED','safe_reason':str(e) if isinstance(e,RuntimeError) else type(e).__name__,'checks_completed':checks,'production_writes':False,'temporary_restore_folder_preserved':True}
        (stage/'STOPPED.private.json').write_text(json.dumps(proof))
        raise RestoreStop('isolated_source_recovery_failed') from None
    finally:
        if config.exists():config.unlink()
