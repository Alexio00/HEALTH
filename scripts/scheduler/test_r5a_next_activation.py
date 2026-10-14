"""R5A: a completed A must not block a separately approved B.

Exercise the actual complete_pipeline.run('activate') path with synthetic
Drive transport, archived metadata, fresh restore proof and no network.
"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import complete_pipeline as pipeline
from drive_cloud_journal import DriveCloudJournal
from drive_rotation import HEALTH_PARENT
from test_drive_rotation import FakeDrive, PARENT, NEW, OLD, SHA
from test_activation_done_entrypoint import FakeCloud, PRODUCER, EXECUTOR, restored

A_DIGEST = 'b' * 64


class ApprovedNextActivationTests(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.root = Path(self.t.name)
        self.root.chmod(0o700)
        self.drive = FakeDrive()
        self.drive.objects[PARENT]['name'] = 'CompleteSets'
        self.drive.objects[PARENT]['parents'] = [HEALTH_PARENT]
        self.drive.objects[NEW]['appProperties']['health_pipeline_commit'] = PRODUCER
        self.cloud = FakeCloud(self.drive, self.root)
        journal = DriveCloudJournal(self.drive, PARENT, self.root/'setup.sqlite', serialized=True)
        try:
            journal.plan(OLD, PARENT, A_DIGEST, [])
            journal.state(OLD, 'DONE', [])
        finally:
            journal.close()
        self.assertFalse(self.drive.objects[OLD]['trashed'])
        self.assertEqual(self.drive.objects[OLD]['appProperties']['health_recovery_state'], 'ACTIVE')
        self.assertEqual(self.drive.objects[NEW]['appProperties']['health_recovery_state'], 'CANDIDATE')

    def execute(self, approved=SHA):
        with patch.dict('os.environ', {
            'RCLONE_CONFIG_CONTENT': 'synthetic-only',
            'HEALTH_COMPLETE_RECOVERY_RCLONE': 'synthetic-independent-reader',
            'HEALTH_RELEASE_CANDIDATE_SHA256': approved,
        }), patch.object(pipeline, 'require_release_context'), patch.object(
            pipeline, 'private', side_effect=lambda path, fresh=False: Path(path)
        ), patch.object(
            pipeline, 'executor_binding', return_value=(EXECUTOR, {'synthetic.py': 'f'*64})
        ), patch.object(
            pipeline, 'CompleteCloud', side_effect=lambda config, root: self.cloud
        ), patch.object(
            pipeline, 'recover_archive', return_value=restored()
        ):
            return pipeline.run('activate', self.root, PRODUCER, serialized=True)

    def test_done_A_then_approved_distinct_B_activates_and_retires_A(self):
        result = self.execute()
        self.assertEqual(result['status'], 'ACTUAL_VERIFIED_COMPLETE_BACKUP_ROTATION_PASS')
        self.assertEqual(result['archive_sha256'], SHA)
        self.assertFalse(result['activation_marker_reconciled'])
        self.assertEqual(result['rotation']['previous_sets_trashed'], 1)
        self.assertEqual(self.drive.objects[NEW]['appProperties']['health_recovery_state'], 'ACTIVE')
        self.assertTrue(self.drive.objects[OLD]['trashed'])
        row = DriveCloudJournal(self.drive, PARENT, self.root/'inspect.sqlite', serialized=True)
        try:
            self.assertEqual(row.read()['target'], NEW)
            self.assertEqual(row.read()['state'], 'DONE')
        finally:
            row.close()

    def test_unapproved_B_does_not_replace_A_journal(self):
        initial = list(self.drive.patches)
        with self.assertRaisesRegex(pipeline.SourceStop, 'completed_rotation_conflicting_candidate'):
            self.execute('e'*64)
        self.assertEqual(self.drive.patches, initial)
        self.assertFalse(self.drive.objects[OLD]['trashed'])

    def test_same_digest_rival_B_cannot_displace_replay_A(self):
        self.drive.objects[NEW]['appProperties']['health_archive_sha256'] = A_DIGEST
        initial = list(self.drive.patches)
        with self.assertRaisesRegex(pipeline.SourceStop, 'completed_rotation_conflicting_candidate'):
            self.execute(A_DIGEST)
        self.assertEqual(self.drive.patches, initial)
        self.assertFalse(self.drive.objects[OLD]['trashed'])

    def test_foreign_producer_B_is_rejected_before_mutation(self):
        self.drive.objects[NEW]['appProperties']['health_pipeline_commit'] = 'c'*40
        initial = list(self.drive.patches)
        with self.assertRaisesRegex(pipeline.SourceStop, 'candidate_producer_sha_or_archive_binding_mismatch'):
            self.execute()
        self.assertEqual(self.drive.patches, initial)
        self.assertFalse(self.drive.objects[OLD]['trashed'])


if __name__ == '__main__':
    unittest.main()
