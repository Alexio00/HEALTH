"""Bind extracted Source bytes, SQL graph and frozen original lineage again."""
import json,re
from complete_archive import digest,relative
from complete_sources import FROZEN_SHA,SourceStop,verify_source_graph

def verify_payload(root,manifest):
    database=root/'database';metadata=root/'metadata';corpus=root/'sources'
    capture=json.loads((database/'capture.private.json').read_text(encoding='utf-8'))
    rows=json.loads((metadata/'source-manifest.private.json').read_text(encoding='utf-8'))
    graph=json.loads((database/'source-graph.private.json').read_text(encoding='utf-8'))
    dump=digest(database/'database.custom');graph_sha=digest(database/'source-graph.private.json')
    if dump!=manifest['database_dump_sha256'] or graph_sha!=manifest['source_graph_sha256'] or rows['database_dump_sha256']!=dump or rows['db_source_graph_sha256']!=graph_sha:
        raise SourceStop('recovery_source_database_binding_changed')
    if capture['dumps']['database.custom']['sha256']!=dump:raise SourceStop('recovery_capture_dump_changed')
    objects=rows.get('objects');paths=set();aliases=set();ids=set();covered=set()
    if not isinstance(objects,list) or not objects or len(objects)>100000:raise SourceStop('recovery_source_inventory_rejected')
    for row in objects:
        name=row['path'];relative('sources/'+name)
        if name.casefold() in aliases or row['primary_object_id'] in ids or not re.fullmatch('[A-Za-z0-9_-]{8,128}',row['primary_object_id']):raise SourceStop('recovery_source_alias_or_identity_rejected')
        size=row['size_bytes'];sha=row['sha256']
        if not isinstance(size,int) or isinstance(size,bool) or size<0 or not re.fullmatch('[a-f0-9]{64}',sha):raise SourceStop('recovery_source_binding_rejected')
        file=corpus/name
        if file.is_symlink() or not file.is_file() or not file.resolve().is_relative_to(corpus.resolve()) or file.stat().st_size!=size or digest(file)!=sha:raise SourceStop('recovery_source_bytes_changed')
        paths.add(name);aliases.add(name.casefold());ids.add(row['primary_object_id']);covered.add((sha,size))
    if any(p.is_symlink() for p in corpus.rglob('*')) or {p.relative_to(corpus).as_posix() for p in corpus.rglob('*') if p.is_file()}!=paths:
        raise SourceStop('recovery_source_corpus_not_exact')
    bound=verify_source_graph(graph,objects)
    frozen=metadata/'frozen-original-inventory.private.json'
    if digest(frozen)!=FROZEN_SHA or manifest.get('frozen_original_inventory_sha256')!=FROZEN_SHA:raise SourceStop('recovery_frozen_lineage_pin_changed')
    originals=json.loads(frozen.read_text(encoding='utf-8-sig'))['objects']
    if len(originals)!=272 or any((x['sha256'],x['size']) not in covered for x in originals):raise SourceStop('recovery_original_content_missing')
    return {'status':'ACTUAL_COMPLETE_SOURCE_ARCHIVE_BINDINGS_PASS','source_corpus_files':len(objects),'source_ids_bound':bound,'frozen_original_content_covered':272,'all_source_bytes_sha_size_verified':True,'provider_recreation':'NOT_RUN','capture_role':capture.get('capture_role'),'restricted_capture_role_enforced':capture.get('restricted_role_enforced',False)}
