import copy
import hashlib
import json
import pathlib
import tempfile
import unittest
import zipfile
from verify_recovery_artifact import TABLES,verify,digest

class RecoveryBindings(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        self.operation='11111111-1111-4111-8111-111111111111';self.package='b'*64;self.pin='c'*40
        self.fp={t:'d'*64 for t in TABLES}
        self.manifest={'medical_table_fingerprints':self.fp}
        self.source={'version':2,'source_corpus_path':'source-corpora/2026-10-11T09-00-00Z','objects':[{'synthetic':True}],'historical_objects':[{'synthetic':True}],'historical_sources_manifest_sha256':'e'*64}
        self.write('MANIFEST',self.manifest);self.write('source.json',self.source)
        self.proof={'restore_run_id':'123','restore_run_attempt':1,'restore_run_head_sha':self.pin,'operation_id':self.operation,'package_fingerprint':self.package,'database_restore_status':'PASS','source_backup_status':'PASS','backup_snapshot_id':'2026-10-11T09-00-00Z','source_corpus_path':self.source['source_corpus_path'],'backup_manifest_sha256':digest(self.root/'MANIFEST'),'source_manifest_path':'source-manifests/synthetic.json','source_manifest_sha256':digest(self.root/'source.json'),'historical_sources_manifest_sha256':'e'*64,'source_count':1,'historical_source_count':1,'restored_table_fingerprints':self.fp}
        self.sidecar={**self.proof,'verified_sources':1,'verified_historical_sources':1}
        self.refresh()
    def write(self,name,data):
        (self.root/name).write_text(json.dumps(data,sort_keys=True),encoding='utf-8')
    def refresh(self):
        self.write('proof.json',self.proof);self.write('SOURCE-EVIDENCE.json',self.sidecar)
        self.att={'schema_version':1,'restore_run_id':'123','restore_run_attempt':1,'restore_run_head_sha':self.pin,'restore_evidence_sha256':digest(self.root/'proof.json')}
        self.zip()
    def zip(self,extra=False):
        with zipfile.ZipFile(self.root/'artifact.zip','w') as z:
            z.writestr('health-restore-attestation.json',json.dumps(self.att))
            if extra:z.writestr('../foreign.json','{}')
    def run_verify(self,artifact_sha=None):
        return verify(self.root/'artifact.zip',artifact_sha or digest(self.root/'artifact.zip'),self.root/'proof.json',self.root/'MANIFEST',self.root/'source.json',self.root/'SOURCE-EVIDENCE.json','123',1,self.pin,self.operation,self.package)
    def test_positive_no_authorization(self):
        r=self.run_verify();self.assertEqual(r['status'],'PASS_OFFLINE_DIGEST_BINDINGS_ONLY');self.assertFalse(r['cutover_authorized']);self.assertEqual(r['source_bytes_readback'],'NOT_CHECKED')
    def test_wrong_artifact_digest(self):
        with self.assertRaisesRegex(ValueError,'artifact digest'):self.run_verify('0'*64)
    def test_proof_tamper(self):
        self.write('proof.json',{**self.proof,'source_count':999})
        with self.assertRaisesRegex(ValueError,'proof digest'):self.run_verify()
    def test_foreign_operation_even_rehashed(self):
        self.proof['operation_id']='22222222-2222-4222-8222-222222222222';self.refresh()
        with self.assertRaisesRegex(ValueError,'foreign migration'):self.run_verify()
    def test_wrong_producer(self):
        self.att['restore_run_head_sha']='f'*40;self.zip()
        with self.assertRaisesRegex(ValueError,'run/pin'):self.run_verify()
    def test_missing_table_even_rehashed(self):
        del self.proof['restored_table_fingerprints']['records'];self.refresh()
        with self.assertRaisesRegex(ValueError,'15 restored'):self.run_verify()
    def test_restore_not_pass(self):
        self.proof['database_restore_status']='FAIL';self.refresh()
        with self.assertRaisesRegex(ValueError,'restore not PASS'):self.run_verify()
    def test_manifest_tamper(self):
        self.write('MANIFEST',{'medical_table_fingerprints':{}})
        with self.assertRaisesRegex(ValueError,'backup manifest'):self.run_verify()
    def test_sidecar_foreign_snapshot(self):
        self.sidecar['backup_snapshot_id']='2026-10-10T09-00-00Z';self.refresh()
        with self.assertRaisesRegex(ValueError,'sidecar'):self.run_verify()
    def test_wrong_counts(self):
        self.sidecar['verified_historical_sources']=9;self.refresh()
        with self.assertRaisesRegex(ValueError,'Historical counts'):self.run_verify()
    def test_extra_zip_member(self):
        self.zip(extra=True)
        with self.assertRaisesRegex(ValueError,'unexpected artifact'):self.run_verify()

if __name__=='__main__':unittest.main()
