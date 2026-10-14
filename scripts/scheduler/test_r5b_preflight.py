"""R5B negative probes for ACTIVE and old binding drift during restore.

No real Drive or medical payload: original DriveRotation / DriveCloudJournal
against the in-memory synthetic FakeDrive transport.
"""
import copy
import tempfile
import unittest
from pathlib import Path
from drive_cloud_journal import DriveCloudJournal
from drive_rotation import DriveRotation, RotationStop
from test_drive_rotation import FakeDrive, PARENT, NEW, OLD, SHA


class PreMutationSafetyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        root.chmod(0o700)
        self.fake = FakeDrive()
        self.journal = DriveCloudJournal(self.fake, PARENT, root/'cloud.sqlite', serialized=True)
        self.addCleanup(self.journal.close)
        self.rotation = DriveRotation(self.fake, PARENT, self.journal, test=True)

    def good_proof(self):
        return {'status': 'ACTUAL_SYNTHETIC_SET_BYTES_READBACK_PASS', 'archive_sha256': SHA}

    def add_rival_active(self):
        rival = copy.deepcopy(self.fake.objects[OLD])
        rival['id'] = 'syntheticrival123'
        rival['name'] = 'complete-20261014T000000Z-deadbeef'
        rival['trashed'] = False
        self.fake.objects[rival['id']] = rival

    def assert_not_promoted_or_trashed(self):
        self.assertEqual(self.fake.objects[NEW]['appProperties']['health_recovery_state'], 'CANDIDATE')
        self.assertFalse(self.fake.objects[OLD]['trashed'])
        self.assertEqual(self.journal.read()['state'], 'PLANNED')
        self.assertEqual([i for i,_ in self.fake.patches if i in (NEW,OLD)], [])

    def test_r5b_h01_rival_during_restore_must_not_patch(self):
        def restore(target):
            self.add_rival_active()
            return self.good_proof()
        with self.assertRaisesRegex(RotationStop, 'rotation_active_inventory_changed'):
            self.rotation.promote(NEW, SHA, restore)
        self.assert_not_promoted_or_trashed()

    def test_r5b_h02_old_digest_during_restore_must_not_patch(self):
        def restore(target):
            self.fake.objects[OLD]['appProperties']['health_archive_sha256'] = 'c'*64
            return self.good_proof()
        with self.assertRaisesRegex(RotationStop, 'complete_set_digest_binding_rejected'):
            self.rotation.promote(NEW, SHA, restore)
        self.assert_not_promoted_or_trashed()

    def test_rival_after_new_active_prevents_trash_and_done(self):
        original = self.fake.request
        injected = {'value': False}
        def race(path, method='GET', body=None, **kwargs):
            result = original(path, method=method, body=body, **kwargs)
            if method=='PATCH' and '/'+NEW+'?' in path and not injected['value']:
                self.add_rival_active()
                injected['value'] = True
            return result
        self.fake.request = race
        with self.assertRaisesRegex(RotationStop, 'rotation_active_inventory_changed'):
            self.rotation.promote(NEW, SHA, lambda _: self.good_proof())
        self.assertTrue(injected['value'])
        self.assertFalse(self.fake.objects[OLD]['trashed'])
        self.assertNotEqual(self.journal.read()['state'], 'DONE')
        self.assertEqual([i for i,_ in self.fake.patches if i==OLD], [])

    def test_normal_rotation_still_completes(self):
        result = self.rotation.promote(NEW, SHA, lambda _: self.good_proof())
        self.assertEqual(result['status'], 'ONE_VERIFIED_ACTIVE_COMPLETE_SET_ROTATION_PASS')
        self.assertEqual(self.journal.read()['state'], 'DONE')
        self.assertTrue(self.fake.objects[OLD]['trashed'])

    def test_rival_after_trash_prevents_terminal_done(self):
        original = self.fake.request
        injected = {'value': False}
        def race(path, method='GET', body=None, **kwargs):
            result = original(path, method=method, body=body, **kwargs)
            if method=='PATCH' and '/'+OLD+'?' in path and not injected['value']:
                self.add_rival_active()
                injected['value'] = True
            return result
        self.fake.request = race
        with self.assertRaisesRegex(RotationStop, 'rotation_active_inventory_changed'):
            self.rotation.promote(NEW, SHA, lambda _: self.good_proof())
        self.assertTrue(injected['value'])
        self.assertTrue(self.fake.objects[OLD]['trashed'])
        self.assertNotEqual(self.journal.read()['state'], 'DONE')


if __name__ == '__main__':
    unittest.main()
