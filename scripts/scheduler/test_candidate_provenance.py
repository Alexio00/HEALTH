"""Synthetic candidate-provenance safety checks; no network or medical data."""
import unittest
from complete_pipeline import require_candidate_binding, SourceStop

class CandidateProvenanceTests(unittest.TestCase):
    SHA='a'*40
    DIGEST='b'*64
    def valid(self):
        return {
            'health_complete_set':'v1',
            'health_pipeline_commit':self.SHA,
            'health_archive_sha256':self.DIGEST,
            'health_recovery_state':'CANDIDATE',
        }
    def test_current_candidate_accepted(self):
        require_candidate_binding(self.valid(),self.SHA,self.DIGEST)
    def test_active_same_sha_accepted(self):
        props=self.valid();props['health_recovery_state']='ACTIVE'
        require_candidate_binding(props,self.SHA,self.DIGEST)
    def test_foreign_old_scheduler_candidate_rejected(self):
        props=self.valid();props['health_pipeline_commit']='c'*40
        with self.assertRaisesRegex(SourceStop,'candidate_producer_sha_or_archive_binding_mismatch'):
            require_candidate_binding(props,self.SHA,self.DIGEST)
    def test_changed_archive_and_missing_owner_metadata_rejected(self):
        for key,value in [('health_complete_set','v2'),('health_archive_sha256','f'*64),('health_recovery_state','TRASHED'),('health_pipeline_commit',None)]:
            with self.subTest(key=key),self.assertRaises(SourceStop):
                props=self.valid();props[key]=value
                require_candidate_binding(props,self.SHA,self.DIGEST)
        with self.assertRaises(SourceStop):
            require_candidate_binding({},self.SHA,self.DIGEST)
if __name__=='__main__':unittest.main()
