"""Exercise the actual pipeline activate entrypoint against a completed rotation.

Synthetic Google Drive + deterministic restore fixtures only. A DONE journal
alone must never bypass the exact old binding/Trash checks in DriveRotation.
"""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import complete_pipeline as pipeline
from drive_cloud_journal import DriveCloudJournal
from drive_rotation import DriveRotation, RotationStop, HEALTH_PARENT
from test_drive_rotation import FakeDrive, PARENT, NEW, OLD, SHA

PRODUCER = 'b' * 40
EXECUTOR = 'e' * 64


def restored():
    return dict(
        status='ACTUAL_COMPLETE_SET_RESTORE_PASS',
        archive_sha256=SHA,
        all_members_verified=True,
        database_restore_pass=True,
        auth_http_pass=True,
        source_rebind_pass=True,
        source_archive={
            'restricted_capture_role_enforced': True,
            'capture_role': 'health_backup_reader',
        },
    )


class FakeCloud:
    def __init__(self, transport, root):
        self.t = transport
        self.parent = PARENT
        self.root = root

    def meta(self, id):
        return copy.deepcopy(self.t.objects[id])

    def children(self, parent):
        return [
            copy.deepcopy(m) for m in self.t.objects.values()
            if m.get('parents') == [parent] and m.get('trashed') is False
        ]

    def download(self, target, sha, label):
        if (target, sha, label) != (NEW, SHA, 'remote-roundtrip'):
            raise AssertionError('unexpected_download')
        path = self.root / 'synthetic-archive.zip'
        path.write_bytes(b'synthetic-fixture-not-a-real-archive')
        return path

    def close(self):
        pass


class ActivationEntrypointDoneTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.root.chmod(0o700)
        self.transport = FakeDrive()
        self.transport.objects[PARENT]['name'] = 'CompleteSets'
        self.transport.objects[PARENT]['parents'] = [HEALTH_PARENT]
        self.transport.objects[NEW]['appProperties']['health_pipeline_commit'] = PRODUCER
        self.cloud = FakeCloud(self.transport, self.root)
        journal = DriveCloudJournal(self.transport, PARENT, self.root / 'setup.sqlite', serialized=True)
        try:
            result = DriveRotation(self.transport, PARENT, journal, verification='full').promote(
                NEW, SHA, lambda _: restored()
            )
            self.assertEqual(result['previous_sets_trashed'], 1)
            self.assertEqual(journal.read()['state'], 'DONE')
        finally:
            journal.close()
        self.patches_before = list(self.transport.patches)

    def execute(self):
        with patch.dict('os.environ', {
            'RCLONE_CONFIG_CONTENT': 'synthetic-only',
            'HEALTH_COMPLETE_RECOVERY_RCLONE': 'synthetic-independent-reader',
            'HEALTH_RELEASE_CANDIDATE_SHA256': SHA,
        }), patch.object(pipeline, 'require_release_context'), patch.object(
            pipeline, 'private', side_effect=lambda path, fresh=False: Path(path)
        ), patch.object(
            pipeline, 'executor_binding', return_value=(EXECUTOR, {'synthetic.py': 'f' * 64})
        ), patch.object(
            pipeline, 'CompleteCloud', side_effect=lambda config, root: self.cloud
        ), patch.object(
            pipeline, 'recover_archive', return_value=restored()
        ):
            return pipeline.run('activate', self.root, PRODUCER, serialized=True)

    def test_healthy_done_replay_rechecks_without_retrashing(self):
        result = self.execute()
        self.assertEqual(result['status'], 'ACTUAL_VERIFIED_COMPLETE_BACKUP_ROTATION_PASS')
        self.assertTrue(result['activation_marker_reconciled'])
        self.assertEqual(result['rotation']['previous_sets_trashed'], 1)
        self.assertEqual([id for id, _ in self.transport.patches[len(self.patches_before):]], [PARENT])
        self.assertTrue(self.transport.objects[OLD]['trashed'])

    def test_old_digest_changes_after_done_must_refuse_activation(self):
        self.transport.objects[OLD]['appProperties']['health_archive_sha256'] = 'c' * 64
        with self.assertRaisesRegex(RotationStop, 'complete_set_digest_binding_rejected'):
            self.execute()
        self.assertEqual(self.transport.patches, self.patches_before)
        self.assertNotIn('health_full_restore_archive', self.transport.objects[PARENT]['appProperties'])

    def test_done_rejects_physical_zip_checksum_not_just_folder_binding(self):
        self.transport.objects[OLD + 'file']['sha256Checksum'] = 'c' * 64
        with self.assertRaisesRegex(RotationStop, 'complete_set_physical_archive_checksum_rejected'):
            self.execute()
        self.assertEqual(self.transport.patches, self.patches_before)
        self.assertEqual(self.transport.objects[OLD]['appProperties']['health_archive_sha256'], 'b' * 64)
        self.assertNotIn('health_full_restore_archive', self.transport.objects[PARENT]['appProperties'])

    def test_old_archive_returns_from_trash_must_refuse_activation(self):
        self.transport.objects[OLD]['trashed'] = False
        with self.assertRaisesRegex(RotationStop, 'completed_rotation_old_not_trashed'):
            self.execute()
        self.assertEqual(self.transport.patches, self.patches_before)

    def test_old_archive_permissions_changed_must_refuse_activation(self):
        self.transport.objects[OLD]['permissions'].append(
            {'type': 'anyone', 'role': 'reader'}
        )
        with self.assertRaisesRegex(RotationStop, 'private_backup_owner_acl_required'):
            self.execute()
        self.assertEqual(self.transport.patches, self.patches_before)

    def test_promoted_done_valid_history_reconciles(self):
        self.transport.objects[PARENT]['appProperties']['health_r_state'] = 'PROMOTED'
        result = self.execute()
        self.assertEqual(result['status'], 'ACTUAL_VERIFIED_COMPLETE_BACKUP_ROTATION_PASS')
        self.assertEqual(result['rotation']['previous_sets_trashed'], 1)
        self.assertEqual(self.transport.objects[PARENT]['appProperties']['health_r_state'], 'DONE')
        self.assertEqual([id for id, payload in self.transport.patches
                          if id == OLD and 'trashed' in payload], [OLD])

    def test_promoted_done_changed_old_digest_rejects_before_marker(self):
        self.transport.objects[PARENT]['appProperties']['health_r_state'] = 'PROMOTED'
        self.transport.objects[OLD]['appProperties']['health_archive_sha256'] = 'c' * 64
        with self.assertRaisesRegex(RotationStop, 'complete_set_digest_binding_rejected'):
            self.execute()
        self.assertNotIn('health_full_restore_archive', self.transport.objects[PARENT]['appProperties'])
        self.assertEqual(self.transport.objects[PARENT]['appProperties']['health_r_state'], 'PROMOTED')
        self.assertEqual(self.transport.patches, self.patches_before)

    def test_promoted_done_rejects_changed_physical_zip_checksum(self):
        self.transport.objects[PARENT]['appProperties']['health_r_state'] = 'PROMOTED'
        self.transport.objects[OLD + 'file']['sha256Checksum'] = 'c' * 64
        with self.assertRaisesRegex(RotationStop, 'complete_set_physical_archive_checksum_rejected'):
            self.execute()
        self.assertEqual(self.transport.patches, self.patches_before)
        self.assertEqual(self.transport.objects[PARENT]['appProperties']['health_r_state'], 'PROMOTED')
        self.assertNotIn('health_full_restore_archive', self.transport.objects[PARENT]['appProperties'])

    def test_promoted_done_old_state_changed_rejects_before_marker(self):
        self.transport.objects[PARENT]['appProperties']['health_r_state'] = 'PROMOTED'
        self.transport.objects[OLD]['appProperties']['health_recovery_state'] = 'CANDIDATE'
        with self.assertRaisesRegex(RotationStop, 'completed_rotation_old_state_changed'):
            self.execute()
        self.assertEqual(self.transport.objects[PARENT]['appProperties']['health_r_state'], 'PROMOTED')
        self.assertEqual(self.transport.patches, self.patches_before)

    def test_done_replay_rejects_foreign_same_digest_candidate(self):
        rival = copy.deepcopy(self.transport.objects[NEW])
        rival.update(id='syntheticrival1234',
                     name='complete-20261013T000000Z-deadbeef')
        rival['appProperties']['health_recovery_state'] = 'CANDIDATE'
        self.transport.objects[rival['id']] = rival
        with self.assertRaisesRegex(pipeline.SourceStop, 'completed_rotation_conflicting_candidate'):
            self.execute()
        self.assertEqual(self.transport.patches, self.patches_before)
        self.assertTrue(self.transport.objects[OLD]['trashed'])
        self.assertNotIn('health_full_restore_archive', self.transport.objects[PARENT]['appProperties'])

    def test_promoted_replay_rejects_foreign_candidate(self):
        self.transport.objects[PARENT]['appProperties']['health_r_state'] = 'PROMOTED'
        rival = copy.deepcopy(self.transport.objects[NEW])
        rival.update(id='syntheticrival1234',
                     name='complete-20261013T000000Z-deadbeef')
        rival['appProperties']['health_recovery_state'] = 'CANDIDATE'
        self.transport.objects[rival['id']] = rival
        with self.assertRaisesRegex(pipeline.SourceStop, 'pending_rotation_foreign_candidate'):
            self.execute()
        self.assertEqual(self.transport.objects[PARENT]['appProperties']['health_r_state'], 'PROMOTED')
        self.assertEqual(self.transport.patches, self.patches_before)



if __name__ == '__main__':
    unittest.main()
