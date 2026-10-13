"""Fresh complete recovery executor for an exact locally downloaded ZIP.

Recovery writing is separate from read-only daily capture. It needs explicitly
supplied primary Writer and independent backup-reader configuration, creates
only a new disposable Drive folder, then trashes it after successful checks.
"""
import json
from complete_archive import verify_archive
from complete_sources import private
from complete_db_restore import restore_database,cleanup
from complete_auth_restore import restore_auth
from complete_source_restore import restore_sources
from complete_payload import verify_payload

def recover_archive(archive,expected_sha,root,recovery_config=None):
    root=private(root,fresh=True)
    extracted=root/'extracted';extracted.mkdir(mode=0o700)
    archive_proof,manifest=verify_archive(archive,expected_sha,extracted)
    source_archive=verify_payload(extracted,manifest)
    database_attempt=root/'database-attempt';database_attempt.mkdir(mode=0o700)
    context=None
    try:
        context=restore_database(extracted/'database',database_attempt)
        auth_attempt=root/'auth-attempt';auth_attempt.mkdir(mode=0o700)
        auth=restore_auth(context,auth_attempt)
        proof={'status':'ACTUAL_COMPLETE_ARCHIVE_DATABASE_AUTH_RESTORE_PASS',
            'candidate_id':manifest['candidate_id'],'archive_sha256':expected_sha,
            'all_members_verified':True,'database_restore_pass':True,'auth_http_pass':True,
            'source_rebind_pass':False,'archive':archive_proof,'database':context['proof'],'auth':auth,
            'source_corpus_bytes_verified':True,'source_graph_binding_verified':True,'source_archive':source_archive,
            'production_clinical_writes':False,'production_source_writes':False,
            'daily_backup_activated':False,'rotation_authorized':False}
        if recovery_config is not None:
            source_attempt=root/'source-attempt';source_attempt.mkdir(mode=0o700)
            source=restore_sources(context,recovery_config,source_attempt,expected_sha)
            proof.update(status='ACTUAL_COMPLETE_SET_RESTORE_PASS',source_rebind_pass=True,source=source)
        (root/'recovery-aggregate.json').write_text(json.dumps(proof,indent=2))
        return proof
    finally:
        if context is not None:cleanup(context)
