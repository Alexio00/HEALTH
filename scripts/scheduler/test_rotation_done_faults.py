"""Synthetic lost replies and exact terminal journal replays (no real Drive)."""
import json
import tempfile
import unittest
from pathlib import Path

from drive_cloud_journal import DriveCloudJournal
from drive_rotation import DriveRotation, RotationStop
from test_drive_rotation import FakeDrive, PARENT, NEW, OLD, SHA


class CloudDoneReplayTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.root.chmod(0o700)
        self.fake = FakeDrive()
        self.j = DriveCloudJournal(self.fake, PARENT, self.root / 'cloud.sqlite', serialized=True)
        self.addCleanup(self.j.close)
        self.rotation = DriveRotation(self.fake, PARENT, self.j, test=True)
        self.recovery_count = 0

    def restore(self, target):
        self.assertEqual(target, NEW)
        self.recovery_count += 1
        return {'status': 'ACTUAL_SYNTHETIC_SET_BYTES_READBACK_PASS', 'archive_sha256': SHA}

    def complete(self):
        outcome = self.rotation.promote(NEW, SHA, self.restore)
        self.assertEqual(outcome['previous_sets_trashed'], 1)
        self.assertEqual(self.j.read()['state'], 'DONE')
        self.assertTrue(self.fake.objects[OLD]['trashed'])

    def test_done_retry_is_read_only_and_reverifies(self):
        self.complete()
        patches = list(self.fake.patches)
        outcome = self.rotation.promote(NEW, SHA, self.restore)
        self.assertEqual(outcome['status'], 'ONE_VERIFIED_ACTIVE_COMPLETE_SET_ROTATION_PASS')
        self.assertEqual(self.fake.patches, patches)
        self.assertEqual(self.recovery_count, 2)
        self.assertEqual(self.j.read()['state'], 'DONE')

    def test_lost_done_patch_reply_replay_after_runner_reopen(self):
        original = self.fake.request
        once = {'lost': False}
        def lossy(path, method='GET', body=None, **kwargs):
            response = original(path, method=method, body=body, **kwargs)
            if (not once['lost'] and method == 'PATCH' and
                    path.startswith('/drive/v3/files/' + PARENT + '?') and
                    json.loads(body).get('appProperties', {}).get('health_r_state') == 'DONE'):
                once['lost'] = True
                raise RuntimeError('simulated_provider_reply_lost_after_DONE')
            return response
        self.fake.request = lossy
        with self.assertRaisesRegex(RuntimeError, 'simulated_provider_reply_lost_after_DONE'):
            self.rotation.promote(NEW, SHA, self.restore)
        self.assertEqual(self.j.read()['state'], 'DONE')
        self.assertTrue(self.fake.objects[OLD]['trashed'])
        patches = list(self.fake.patches)
        self.j.close()
        self.j = DriveCloudJournal(self.fake, PARENT, self.root / 'cloud.sqlite', serialized=True)
        self.rotation = DriveRotation(self.fake, PARENT, self.j, test=True)
        result = self.rotation.promote(NEW, SHA, self.restore)
        self.assertEqual(result['previous_sets_trashed'], 1)
        self.assertEqual(self.fake.patches, patches)
        self.assertEqual(self.j.read()['state'], 'DONE')
        self.assertEqual(self.recovery_count, 2)

    def test_done_cannot_hide_old_active(self):
        self.complete()
        self.fake.objects[OLD]['trashed'] = False
        patches = list(self.fake.patches)
        with self.assertRaisesRegex(RotationStop, 'completed_rotation_old_not_trashed'):
            self.rotation.promote(NEW, SHA, self.restore)
        self.assertEqual(self.fake.patches, patches)
        self.assertFalse(self.fake.objects[OLD]['trashed'])

    def test_done_cannot_repromote_downgraded_target(self):
        self.complete()
        self.fake.objects[NEW]['appProperties']['health_recovery_state'] = 'CANDIDATE'
        patches = list(self.fake.patches)
        with self.assertRaisesRegex(RotationStop, 'completed_rotation_binding_rejected'):
            self.rotation.promote(NEW, SHA, self.restore)
        self.assertEqual(self.fake.patches, patches)

    def test_done_requires_fresh_restore(self):
        self.complete()
        patches = list(self.fake.patches)
        with self.assertRaisesRegex(RotationStop, 'complete_new_restore_not_accepted'):
            self.rotation.promote(NEW, SHA, lambda _: {'status': 'OLD_PASS'})
        self.assertEqual(self.fake.patches, patches)

    def test_done_rejects_modified_old_archive_binding(self):
        self.complete()
        self.fake.objects[OLD]['appProperties']['health_archive_sha256'] = 'c' * 64
        patches = list(self.fake.patches)
        with self.assertRaisesRegex(RotationStop, 'complete_set_digest_binding_rejected'):
            self.rotation.promote(NEW, SHA, self.restore)
        self.assertEqual(self.fake.patches, patches)


if __name__ == '__main__':
    unittest.main()
