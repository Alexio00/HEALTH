"""Verify/extract a complete recovery archive; payload and filenames stay private."""
import argparse,hashlib,json,os,re,stat,zipfile
from pathlib import Path,PurePosixPath

LIMIT=8*1024**3
REQUIRED={'database/database.custom','database/schema.sql','database/data.sql',
 'database/roles.private.json','database/role-memberships.private.json',
 'database/role-db-settings.private.json','database/source-graph.private.json',
 'database/capture.private.json','metadata/source-manifest.private.json',
 'metadata/frozen-original-inventory.private.json'}
class ArchiveStop(RuntimeError):pass

def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1048576),b''):h.update(block)
    return h.hexdigest()

def relative(value):
    if not isinstance(value,str) or not value or '\\' in value or ':' in value or any(ord(c)<32 for c in value):raise ArchiveStop('archive_path_rejected')
    p=PurePosixPath(value)
    if p.is_absolute() or '..' in p.parts or str(p)!=value or p.parts[0] not in ('database','metadata','sources'):raise ArchiveStop('archive_path_rejected')
    # Windows aliases must not escape the reviewed archive inventory.
    if any(part.endswith((' ','.')) or re.fullmatch(r'(?i)(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?',part) for part in p.parts):raise ArchiveStop('archive_path_rejected')
    return p

def verify_archive(archive,expected_sha,output=None):
    archive=Path(archive)
    if archive.is_symlink() or not re.fullmatch('[a-f0-9]{64}',expected_sha) or digest(archive)!=expected_sha:raise ArchiveStop('archive_sha256_mismatch')
    if output is not None:
        output=Path(output)
        if output.is_symlink() or not output.is_dir() or any(output.iterdir()):raise ArchiveStop('fresh_private_output_required')
        if os.name!='nt' and output.stat().st_mode&0o077:raise ArchiveStop('private_output_permissions_required')
    with zipfile.ZipFile(archive) as z:
        names=z.namelist()
        if len(names)>100000 or len(set(n.casefold() for n in names))!=len(names):raise ArchiveStop('archive_inventory_not_unique')
        if names.count('manifest.private.json')!=1:raise ArchiveStop('archive_manifest_missing')
        info=z.getinfo('manifest.private.json')
        if info.file_size>8*1024**2:raise ArchiveStop('archive_manifest_too_large')
        manifest=json.loads(z.read(info))
        if manifest.get('schema_version')!=1 or not re.fullmatch(r'complete-[0-9]{8}T[0-9]{6}Z-[a-f0-9]{8}',manifest.get('candidate_id','')):raise ArchiveStop('archive_manifest_version_or_identity_rejected')
        rows=manifest.get('objects',[]);expected={};total=0
        for row in rows:
            name=row['path'];relative(name)
            if name in expected or not isinstance(row.get('bytes'),int) or isinstance(row['bytes'],bool) or row['bytes']<0 or not re.fullmatch('[a-f0-9]{64}',row.get('sha256','')):raise ArchiveStop('archive_member_binding_rejected')
            expected[name]=row;total+=row['bytes']
        if total>LIMIT or set(names)!=(set(expected)|{'manifest.private.json'}) or not REQUIRED.issubset(expected):raise ArchiveStop('archive_complete_inventory_rejected')
        # First verify every member, then write. A bad late member must not leave
        # partially extracted files that could be mistaken for restored input.
        for name,row in expected.items():
            info=z.getinfo(name)
            if info.file_size!=row['bytes'] or info.is_dir() or stat.S_ISLNK(info.external_attr>>16):raise ArchiveStop('archive_member_type_or_size_rejected')
            h=hashlib.sha256();count=0
            with z.open(info) as f:
                for block in iter(lambda:f.read(1048576),b''):
                    count+=len(block)
                    if count>row['bytes']:raise ArchiveStop('archive_member_size_overflow')
                    h.update(block)
            if count!=row['bytes'] or h.hexdigest()!=row['sha256']:raise ArchiveStop('archive_member_sha256_mismatch')
        if expected['database/database.custom']['sha256']!=manifest.get('database_dump_sha256') or expected['database/source-graph.private.json']['sha256']!=manifest.get('source_graph_sha256'):raise ArchiveStop('archive_database_source_graph_binding_rejected')
        if output:
            for name in names:
                target=output/name
                target.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
                with target.open('xb') as dst,z.open(name) as src:
                    for block in iter(lambda:src.read(1048576),b''):dst.write(block)
                if os.name!='nt':target.chmod(0o600)
    return {'status':'COMPLETE_ARCHIVE_SHA_AND_ALL_MEMBERS_PASS','archive_sha256':expected_sha,
     'candidate_id':manifest['candidate_id'],'verified_objects':len(expected)+1,'verified_bytes':total,
     'dump_sha256':manifest['database_dump_sha256'],'isolated_database_restore':'NOT_RUN',
     'rotation_authorized':False},manifest

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--archive',required=True,type=Path);p.add_argument('--expected-sha',required=True);p.add_argument('--private-output',required=True,type=Path);a=p.parse_args()
    try:report,_=verify_archive(a.archive,a.expected_sha,a.private_output);print(json.dumps(report))
    except ArchiveStop as e:print(json.dumps({'status':'STOPPED','safe_reason':str(e)}));raise SystemExit(2)
    except Exception:print(json.dumps({'status':'STOPPED','safe_reason':'archive_validation_failed'}));raise SystemExit(2)
