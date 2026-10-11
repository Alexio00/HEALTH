#!/usr/bin/env python3
"""Offline digest/binding check. No DB, secrets, network, finalization or approval."""
import argparse
import hashlib
import json
import pathlib
import re
import uuid
import zipfile

TABLES = {'records','domains','record_domains','sources','source_locations','record_sources','cases','case_links','analytes','labs','medications','monitoring','plan_items','questions','id_reservations'}

def need(ok, message):
    if not ok:
        raise ValueError(message)

def digest(path):
    h=hashlib.sha256()
    with pathlib.Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):
            h.update(chunk)
    return h.hexdigest()

def read_json(path):
    need(pathlib.Path(path).stat().st_size <= 8*1024*1024,'oversized JSON')
    return json.loads(pathlib.Path(path).read_text(encoding='utf-8'))

def verify(artifact, artifact_sha, proof_file, manifest_file, source_file, sidecar_file,
           run_id, attempt, producer_sha, operation_id, package_fingerprint):
    need(re.fullmatch('[a-f0-9]{64}',artifact_sha) is not None,'invalid artifact SHA')
    need(re.fullmatch('[a-f0-9]{40}',producer_sha) is not None,'invalid producer SHA')
    need(re.fullmatch('[a-f0-9]{64}',package_fingerprint) is not None,'invalid package SHA')
    need(str(uuid.UUID(operation_id))==operation_id,'invalid operation UUID')
    need(re.fullmatch('[1-9][0-9]*',str(run_id)) is not None and type(attempt) is int and attempt>0,'invalid run identity')
    need(digest(artifact)==artifact_sha,'GitHub artifact digest mismatch')
    with zipfile.ZipFile(artifact) as archive:
        names=archive.namelist()
        need(names==['health-restore-attestation.json'],'unexpected artifact members')
        info=archive.getinfo(names[0])
        need(info.file_size<=65536,'oversized attestation')
        att=json.loads(archive.read(info).decode('utf-8'))
    need(type(att.get('schema_version')) is int and att['schema_version']==1,'unsupported attestation schema')
    need(att.get('restore_run_id')==str(run_id) and type(att.get('restore_run_attempt')) is int and att['restore_run_attempt']==attempt and att.get('restore_run_head_sha')==producer_sha,'attestation run/pin mismatch')
    need(att.get('restore_evidence_sha256')==digest(proof_file),'private restore proof digest mismatch')
    proof=read_json(proof_file); manifest=read_json(manifest_file)
    source=read_json(source_file); sidecar=read_json(sidecar_file)
    need(proof.get('restore_run_id')==str(run_id) and proof.get('restore_run_attempt')==attempt and proof.get('restore_run_head_sha')==producer_sha,'proof run mismatch')
    need(proof.get('operation_id')==operation_id and proof.get('package_fingerprint')==package_fingerprint,'foreign migration proof')
    need(proof.get('database_restore_status')=='PASS' and proof.get('source_backup_status')=='PASS','restore not PASS')
    snapshot=proof.get('backup_snapshot_id')
    need(isinstance(snapshot,str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}Z',snapshot) is not None,'invalid backup identity')
    need(proof.get('source_corpus_path')=='source-corpora/'+snapshot,'corpus snapshot mismatch')
    need(proof.get('backup_manifest_sha256')==digest(manifest_file),'backup manifest mismatch')
    need(proof.get('source_manifest_sha256')==digest(source_file),'source manifest mismatch')
    fp=proof.get('restored_table_fingerprints')
    need(isinstance(fp,dict) and set(fp)==TABLES and all(isinstance(v,str) and re.fullmatch('[a-f0-9]{64}',v) is not None for v in fp.values()) and fp==manifest.get('medical_table_fingerprints'),'15 restored fingerprints mismatch')
    need(source.get('version')==2 and source.get('source_corpus_path')==proof.get('source_corpus_path'),'source manifest version/corpus mismatch')
    need(isinstance(source.get('objects'),list) and isinstance(source.get('historical_objects'),list) and bool(source['historical_objects']),'incomplete source manifest')
    need(len(source['objects'])==proof.get('source_count')==sidecar.get('verified_sources'),'Source counts mismatch')
    need(len(source['historical_objects'])==proof.get('historical_source_count')==sidecar.get('verified_historical_sources'),'Historical counts mismatch')
    need(source.get('historical_sources_manifest_sha256')==proof.get('historical_sources_manifest_sha256') and re.fullmatch('[a-f0-9]{64}',str(proof.get('historical_sources_manifest_sha256'))) is not None,'Historical digest mismatch')
    for key in ('operation_id','package_fingerprint','backup_snapshot_id','source_corpus_path','backup_manifest_sha256','source_manifest_path','source_manifest_sha256','historical_sources_manifest_sha256'):
        need(proof.get(key) is not None and proof.get(key)==sidecar.get(key),'source sidecar binding mismatch: '+key)
    return {'status':'PASS_OFFLINE_DIGEST_BINDINGS_ONLY','run_id':str(run_id),'operation_id':operation_id,
            'live_database_match':'NOT_CHECKED','source_bytes_readback':'NOT_CHECKED',
            'owner_approval':'NOT_CHECKED','cutover_authorized':False}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('artifact','artifact-sha','proof','manifest','source-manifest','source-sidecar','run-id','producer-sha','operation-id','package-fingerprint'):
        p.add_argument('--'+name,required=True)
    p.add_argument('--attempt',required=True,type=int)
    a=p.parse_args()
    try:
        result=verify(a.artifact,a.artifact_sha,a.proof,a.manifest,a.source_manifest,a.source_sidecar,a.run_id,a.attempt,a.producer_sha,a.operation_id,a.package_fingerprint)
        print(json.dumps(result,indent=2))
    except (ValueError,OSError,zipfile.BadZipFile,KeyError,TypeError) as e:
        print(json.dumps({'status':'BLOCKED','reason':str(e),'cutover_authorized':False}));raise SystemExit(2)
