"""Read-only primary byte capture and complete candidate packaging.

All paths/configuration/filenames stay in a caller-owned private runtime. This
module never uploads, rotates or accepts a replacement backup. The caller must
serialize with Writer publication before enabling daily capture.
"""
import configparser, datetime, hashlib, json, os, re, subprocess, urllib.error
import urllib.request, uuid, zipfile
from pathlib import Path, PurePosixPath
from complete_archive import REQUIRED, ArchiveStop, digest, relative, verify_archive

PRIMARY_FOLDER = os.environ.get('HEALTH_PRIMARY_SOURCE_FOLDER_ID', '')
FROZEN_SHA = os.environ.get('HEALTH_FROZEN_LINEAGE_SHA256', '')
FROZEN_COUNT = int(os.environ.get('HEALTH_FROZEN_ORIGINAL_COUNT', '0'))
MAX_FILES = 100000
MAX_BYTES = 8 * 1024**3
class SourceStop(RuntimeError): pass

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl): return None

def private(path, fresh=False):
    path = Path(path)
    if path.is_symlink() or not path.is_dir() or fresh and any(path.iterdir()):
        raise SourceStop('private_runtime_directory_rejected')
    if os.name != 'nt' and path.stat().st_mode & 0o077:
        raise SourceStop('private_runtime_permissions_required')
    return path.resolve()

def inventory_binding(items):
    return sorted(({k: x.get(k) for k in ('Path','ID','Size','MimeType','ModTime','Hashes')}
                   for x in items), key=lambda x: x['Path'])

def validate_inventory(items):
    if not isinstance(items, list) or not items or len(items) > MAX_FILES:
        raise SourceStop('primary_inventory_size_rejected')
    paths = {}; aliases = set(); ids = set(); total = 0
    for item in items:
        name = item.get('Path')
        try: relative('sources/' + name)
        except (TypeError, ArchiveStop): raise SourceStop('unsafe_source_path') from None
        alias = name.casefold()
        if alias in aliases or item.get('ID') in ids:
            raise SourceStop('source_path_or_identity_not_unique')
        if not isinstance(item.get('ID'), str) or not re.fullmatch('[A-Za-z0-9_-]{8,128}',item['ID']):
            raise SourceStop('primary_object_identity_rejected')
        size = item.get('Size')
        if not isinstance(size,int) or isinstance(size,bool) or size < 0:
            raise SourceStop('source_size_rejected')
        if item.get('MimeType','').startswith('application/vnd.google-apps.'):
            raise SourceStop('native_or_shortcut_source_requires_explicit_export')
        total += size
        if total > MAX_BYTES: raise SourceStop('source_corpus_size_limit')
        paths[name] = item; aliases.add(alias); ids.add(item['ID'])
    return paths

def verify_source_graph(graph, records):
    by_path = {x['path']: x for x in records}
    if len(by_path) != len(records): raise SourceStop('source_manifest_not_unique')
    locations = [x for x in graph['locations'] if x['location_role']=='PRIMARY' and x['provider']=='google-drive']
    by_source = {x['source_id']: x for x in locations}
    sources = graph['sources']
    if len(by_source) != len(locations) or len({s['source_id'] for s in sources}) != len(sources):
        raise SourceStop('primary_source_graph_not_unique')
    for source in sources:
        obj = by_path.get(source['logical_path']); loc = by_source.get(source['source_id'])
        if not obj or not loc or (obj['sha256'],obj['size_bytes'],obj['primary_object_id']) != (
                source['sha256'],source['size_bytes'],loc['provider_object_id']):
            raise SourceStop('captured_source_graph_byte_identity_mismatch')
    return len(sources)

def provider_hashes(file, inventory_item):
    hashes=inventory_item.get('Hashes') or {}
    supported={'md5':32,'sha1':40,'sha256':64}; checks={}
    for key,value in hashes.items():
        key=key.lower().replace('-','')
        if key in supported and value:
            if not re.fullmatch('[a-fA-F0-9]{'+str(supported[key])+'}',value):
                raise SourceStop('provider_content_hash_rejected')
            checks[key]=hashlib.new(key)
    if not checks:raise SourceStop('primary_binary_content_hash_required')
    with Path(file).open('rb') as f:
        for block in iter(lambda:f.read(1048576),b''):
            for check in checks.values():check.update(block)
    expected={key.lower().replace('-',''):value.lower() for key,value in hashes.items() if value}
    if any(check.hexdigest()!=expected[key] for key,check in checks.items()):
        raise SourceStop('downloaded_source_provider_hash_mismatch')

def capture_sources(database, original_config, output):
    database = private(database); output = private(output, fresh=True)
    cfg = configparser.ConfigParser(interpolation=None)
    cfg.read(original_config, encoding='utf-8')
    if not cfg.has_section('health_primary') or cfg['health_primary'].get('type')!='drive' or cfg['health_primary'].get('scope')!='drive.readonly':
        raise SourceStop('primary_readonly_config_required')
    scoped = configparser.ConfigParser(interpolation=None)
    scoped['complete_primary_reader'] = dict(cfg['health_primary'])
    scoped['complete_primary_reader']['root_folder_id'] = PRIMARY_FOLDER
    config = output/'rclone.private.conf'
    with config.open('x',encoding='utf-8') as file: scoped.write(file)
    config.chmod(0o600)
    def run(command, *args):
        result = subprocess.run(['rclone',command,*map(str,args),'--config',str(config),
            '--log-file',str(output/'rclone.private.log'),'--log-level','ERROR'],capture_output=True,timeout=1800)
        if result.returncode: raise SourceStop('private_drive_read_failed_'+command)
        return result.stdout
    def metadata(path):
        current=configparser.ConfigParser(interpolation=None);current.read(config,encoding='utf-8')
        token=json.loads(current['complete_primary_reader']['token'])['access_token']
        req=urllib.request.Request('https://www.googleapis.com'+path,headers={'Authorization':'Bearer '+token})
        try:
            with urllib.request.build_opener(NoRedirect()).open(req,timeout=30) as response:
                return json.loads(response.read(1048576))
        except Exception: raise SourceStop('primary_identity_metadata_read_failed') from None
    def inventory():
        rows=json.loads(run('lsjson','complete_primary_reader:','--recursive','--hash'))
        return [x for x in rows if not x.get('IsDir')]
    try:
        run('lsf','complete_primary_reader:','--max-depth','1','--dirs-only')
        if metadata('/drive/v3/about?fields=user(emailAddress)')['user']['emailAddress']!=os.environ.get('HEALTH_PRIMARY_DRIVE_OWNER_EMAIL', ''):
            raise SourceStop('primary_reader_identity_rejected')
        root=metadata('/drive/v3/files/'+PRIMARY_FOLDER+'?fields=id,mimeType,trashed')
        if root.get('id')!=PRIMARY_FOLDER or root.get('mimeType')!='application/vnd.google-apps.folder' or root.get('trashed') is not False:
            raise SourceStop('primary_sources_root_rejected')
        before=inventory();paths=validate_inventory(before)
        (output/'before.private.json').write_text(json.dumps(before,ensure_ascii=False),encoding='utf-8')
        corpus=output/'corpus';corpus.mkdir(mode=0o700)
        run('copy','complete_primary_reader:',corpus,'--immutable','--create-empty-src-dirs','--drive-skip-shortcuts')
        files=[p for p in corpus.rglob('*') if p.is_file()]
        if any(p.is_symlink() for p in corpus.rglob('*')) or {p.relative_to(corpus).as_posix() for p in files}!=set(paths):
            raise SourceStop('local_source_inventory_not_exact')
        records=[]
        for name,item in paths.items():
            file=corpus.joinpath(*PurePosixPath(name).parts)
            if file.stat().st_size!=item['Size']:raise SourceStop('local_source_size_mismatch')
            provider_hashes(file,item)
            records.append({'path':name,'primary_object_id':item['ID'],'sha256':digest(file),'size_bytes':item['Size']})
        graph=json.loads((database/'source-graph.private.json').read_text(encoding='utf-8'))
        source_count=verify_source_graph(graph,records)
        after=inventory();validate_inventory(after)
        (output/'after.private.json').write_text(json.dumps(after,ensure_ascii=False),encoding='utf-8')
        if inventory_binding(before)!=inventory_binding(after):raise SourceStop('primary_tree_changed_during_capture')
        capture=json.loads((database/'capture.private.json').read_text())
        manifest={'objects':records,'db_source_graph_sha256':digest(database/'source-graph.private.json'),
                  'database_dump_sha256':capture['dumps']['database.custom']['sha256']}
        file=output/'manifest.private.json';file.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
        return {'status':'ACTUAL_PRIMARY_SOURCE_BYTE_CAPTURE_COMPONENT_PASS','total_corpus_files':len(records),
                'db_sources_bound_by_sha_size_and_primary_id':source_count,'primary_inventory_stable_before_after':True,
                'manifest_sha256':digest(file),'database_dump_sha256':manifest['database_dump_sha256'],
                'production_writes':False,'remote_backup_uploaded':False,'full_replacement_backup_accepted':False}
    finally:
        config.unlink()

def package_candidate(database, source, frozen, output):
    database=private(database);source=private(source);output=private(output,fresh=True)
    frozen=Path(frozen)
    if frozen.is_symlink() or digest(frozen)!=FROZEN_SHA:raise SourceStop('frozen_original_inventory_pin_mismatch')
    capture=json.loads((database/'capture.private.json').read_text())
    if capture.get('status')!='ACTUAL_COHERENT_DB_AUTH_SNAPSHOT_CAPTURED_NOT_RESTORED':raise SourceStop('coherent_capture_required')
    files={name:database/name.split('/',1)[1] for name in REQUIRED if name.startswith('database/')}
    for name,proof in capture['dumps'].items():
        if name not in ('database.custom','schema.sql','data.sql') or digest(database/name)!=proof['sha256'] or (database/name).stat().st_size!=proof['bytes']:
            raise SourceStop('database_capture_binding_mismatch')
    manifest_source=json.loads((source/'manifest.private.json').read_text(encoding='utf-8'))
    if manifest_source['db_source_graph_sha256']!=digest(database/'source-graph.private.json') or manifest_source['database_dump_sha256']!=digest(database/'database.custom'):
        raise SourceStop('source_database_capture_binding_mismatch')
    graph=json.loads((database/'source-graph.private.json').read_text(encoding='utf-8'))
    bound=verify_source_graph(graph,manifest_source['objects'])
    originals=json.loads(frozen.read_text(encoding='utf-8-sig'))['objects']
    covered={(o['sha256'],o['size_bytes']) for o in manifest_source['objects']}
    if len(originals)!=FROZEN_COUNT or any((o['sha256'],o['size']) not in covered for o in originals):
        raise SourceStop('frozen_original_bytes_not_covered')
    files['metadata/source-manifest.private.json']=source/'manifest.private.json'
    files['metadata/frozen-original-inventory.private.json']=frozen
    for row in manifest_source['objects']:
        relative('sources/'+row['path'])
        file=(source/'corpus').joinpath(*PurePosixPath(row['path']).parts)
        if file.is_symlink() or not file.resolve().is_relative_to((source/'corpus').resolve()) or file.stat().st_size!=row['size_bytes'] or digest(file)!=row['sha256']:
            raise SourceStop('source_object_package_recheck_failed')
        files['sources/'+row['path']]=file
    manifest={'schema_version':1,'candidate_id':'complete-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8],
        'state':'CANDIDATE_NOT_ACTIVE','database_dump_sha256':digest(database/'database.custom'),
        'source_graph_sha256':digest(database/'source-graph.private.json'),'frozen_original_inventory_sha256':FROZEN_SHA,
        'original_identities_preserved_as_lineage_metadata':FROZEN_COUNT,'provider_original_ids_recreated':False,
        'all_schema_table_fingerprints':capture['all_schema_table_fingerprints'],
        'restore_acceptance':'NOT_RUN_FOR_THIS_NEW_CANDIDATE',
        'objects':[{'path':n,'sha256':digest(p),'bytes':p.stat().st_size} for n,p in sorted(files.items())]}
    (output/'manifest.private.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    archive=output/'complete-recovery.zip'
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for name,file in sorted(files.items()):z.write(file,name)
        z.write(output/'manifest.private.json','manifest.private.json')
    sha=digest(archive);proof,_=verify_archive(archive,sha)
    proof.update(status='ACTUAL_COMPLETE_CANDIDATE_PACKAGED_NOT_RESTORED',archive_bytes=archive.stat().st_size,
        source_corpus_files=len(manifest_source['objects']),source_ids_bound=bound,frozen_original_identities_content_covered=272,
        all_schema_tables=len(capture['all_schema_table_fingerprints']),auth_tables=len(capture['auth_fingerprints']),
        clinical_tables=len(capture['clinical_fingerprints']),production_writes=False,remote_uploads=False,rotation_enabled=False)
    return proof
