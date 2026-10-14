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

    def test_integrated_preflight_rejects_zip_id_swap_during_restore_before_active(self):
        # #95 R5B pre-mutation gate must enforce #94 exact physical ZIP identity.
        def restored_after_swap(target):
            self.assertEqual(target, NEW)
            original = self.fake.objects.pop(OLD + 'file')
            replacement = dict(original, id='syntheticreplacementzip123')
            self.fake.objects[replacement['id']] = replacement
            return {'status': 'ACTUAL_SYNTHETIC_SET_BYTES_READBACK_PASS',
                    'archive_sha256': SHA}
        with self.assertRaisesRegex(
            RotationStop, 'complete_set_physical_archive_id_binding_rejected'
        ):
            self.rotation.promote(NEW, SHA, restored_after_swap)
        self.assertEqual(self.j.read()['state'], 'PLANNED')
        self.assertEqual(self.fake.objects[NEW]['appProperties']['health_recovery_state'],
                         'CANDIDATE')
        self.assertFalse(self.fake.objects[OLD]['trashed'])
        # Initial durable PLANNED write is mandatory; no ACTIVE/Trash or later
        # journal transition is permitted after the ZIP ID changes.
        self.assertEqual(len(self.fake.patches), 1)
        self.assertEqual(self.fake.patches[0][0], PARENT)
        self.assertEqual(
            self.fake.patches[0][1]['appProperties']['health_r_state'],
            'PLANNED'
        )
        self.assertEqual([i for i, _ in self.fake.patches if i in (NEW, OLD)], [])

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

    def test_done_rejects_physical_zip_checksum_drift_without_metadata_change(self):
        self.complete()
        self.fake.objects[OLD + 'file']['sha256Checksum'] = 'c' * 64
        before = list(self.fake.patches)
        with self.assertRaisesRegex(RotationStop, 'complete_set_physical_archive_checksum_rejected'):
            self.rotation.promote(NEW, SHA, self.restore)
        self.assertEqual(self.j.read()['state'], 'DONE')
        self.assertEqual(self.fake.patches, before)
        self.assertEqual(self.fake.objects[OLD]['appProperties']['health_archive_sha256'], 'b' * 64)

    def replace_retired_zip_with_same_digest_and_size(self):
        original = self.fake.objects.pop(OLD + 'file')
        substitute = dict(original, id='syntheticreplacementzip123')
        self.fake.objects[substitute['id']] = substitute
        self.assertEqual(substitute['sha256Checksum'], 'b' * 64)
        self.assertEqual(substitute['size'], '20')

    def test_done_zip_id_substitution_same_digest_rejected_without_mutations(self):
        self.complete()
        self.replace_retired_zip_with_same_digest_and_size()
        before = self.j.read()
        patches = list(self.fake.patches)
        with self.assertRaisesRegex(RotationStop, 'complete_set_physical_archive_id_binding_rejected'):
            self.rotation.promote(NEW, SHA, self.restore)
        self.assertEqual(self.j.read(), before)
        self.assertEqual(self.fake.patches, patches)
        self.assertTrue(self.fake.objects[OLD]['trashed'])
        self.assertEqual(self.fake.objects[NEW]['appProperties']['health_recovery_state'], 'ACTIVE')

    def test_cloud_journal_persists_zip_id_and_version_2(self):
        self.complete()
        saved=self.fake.objects[PARENT]['appProperties']
        self.assertEqual(saved['health_r_v'],'2')
        self.assertEqual(saved['health_r_old'],OLD)
        self.assertEqual(saved['health_r_old_zip'],OLD+'file')
        self.assertEqual(self.j.read()['state'],'DONE')

    def test_done_missing_zip_binding_in_v2_fails_closed(self):
        self.complete()
        props=self.fake.objects[PARENT]['appProperties']
        props.pop('health_r_old_zip')
        before=dict(props)
        patches=list(self.fake.patches)
        with self.assertRaisesRegex(RotationStop,'cloud_journal_old_zip_id_binding_required'):
            self.rotation.promote(NEW,SHA,self.restore)
        self.assertEqual(props,before)
        self.assertEqual(self.fake.patches,patches)

    def test_done_legacy_v1_no_zip_binding_fails_closed(self):
        self.complete()
        properties = self.fake.objects[PARENT]['appProperties']
        properties['health_r_v'] = '1'
        properties.pop('health_r_old_zip')
        before = dict(properties)
        patches = list(self.fake.patches)
        with self.assertRaisesRegex(RotationStop, 'cloud_journal_old_zip_id_binding_required'):
            self.rotation.promote(NEW, SHA, self.restore)
        self.assertEqual(properties, before)
        self.assertEqual(self.fake.patches, patches)

    def test_done_rejects_physical_zip_size_drift(self):
        self.complete()
        self.fake.objects[OLD + 'file']['size'] = '21'
        before = list(self.fake.patches)
        with self.assertRaisesRegex(RotationStop, 'complete_set_physical_archive_size_rejected'):
            self.rotation.promote(NEW, SHA, self.restore)
        self.assertEqual(self.j.read()['state'], 'DONE')
        self.assertEqual(self.fake.patches, before)

    def test_done_fails_closed_when_trashed_zip_inaccessible(self):
        self.complete()
        self.fake.objects.pop(OLD + 'file')
        before = list(self.fake.patches)
        with self.assertRaisesRegex(RotationStop, 'complete_set_physical_archive_identity_rejected'):
            self.rotation.promote(NEW, SHA, self.restore)
        self.assertEqual(self.j.read()['state'], 'DONE')
        self.assertEqual(self.fake.patches, before)

    def test_done_missing_physical_zip_checksum_fails_closed(self):
        self.complete()
        self.fake.objects[OLD + 'file'].pop('sha256Checksum')
        before = list(self.fake.patches)
        with self.assertRaisesRegex(RotationStop, 'complete_set_physical_archive_checksum_rejected'):
            self.rotation.promote(NEW, SHA, self.restore)
        self.assertEqual(self.j.read()['state'], 'DONE')
        self.assertEqual(self.fake.patches, before)

    def promoted_done(self):
        self.j.plan(NEW, PARENT, SHA, [{'id': OLD, 'sha': 'b' * 64, 'zip_id': OLD + 'file'}])
        self.fake.objects[NEW]['appProperties']['health_recovery_state'] = 'ACTIVE'
        self.fake.objects[OLD]['trashed'] = True
        self.j.state(NEW, 'PROMOTED', [OLD])
        self.assertEqual(self.j.read()['state'], 'PROMOTED')

    def test_promoted_done_replay_is_safe_and_idempotent(self):
        self.promoted_done()
        prior = list(self.fake.patches)
        result = self.rotation.promote(NEW, SHA, self.restore)
        self.assertEqual(result['previous_sets_trashed'], 1)
        self.assertEqual(self.j.read()['state'], 'DONE')
        self.assertEqual(
            sum(id == OLD and 'trashed' in patch for id, patch in self.fake.patches),
            0
        )
        self.assertEqual(self.recovery_count, 1)
        self.assertGreater(len(self.fake.patches), len(prior))

    def test_promoted_done_rejects_old_digest_drift_without_patch(self):
        self.promoted_done()
        self.fake.objects[OLD]['appProperties']['health_archive_sha256'] = 'c' * 64
        before = list(self.fake.patches)
        with self.assertRaisesRegex(RotationStop, 'complete_set_digest_binding_rejected'):
            self.rotation.promote(NEW, SHA, self.restore)
        self.assertEqual(self.j.read()['state'], 'PROMOTED')
        self.assertEqual(self.fake.patches, before)

    def test_promoted_done_rejects_physical_zip_checksum_drift_without_patch(self):
        self.promoted_done()
        self.fake.objects[OLD + 'file']['sha256Checksum'] = 'c' * 64
        before = list(self.fake.patches)
        with self.assertRaisesRegex(RotationStop, 'complete_set_physical_archive_checksum_rejected'):
            self.rotation.promote(NEW, SHA, self.restore)
        self.assertEqual(self.j.read()['state'], 'PROMOTED')
        self.assertEqual(self.fake.patches, before)
        self.assertEqual(self.fake.objects[OLD]['appProperties']['health_archive_sha256'], 'b' * 64)

    def test_promoted_done_zip_id_substitution_same_digest_rejected_without_mutations(self):
        self.promoted_done()
        self.replace_retired_zip_with_same_digest_and_size()
        before = self.j.read()
        patches = list(self.fake.patches)
        with self.assertRaisesRegex(RotationStop, 'complete_set_physical_archive_id_binding_rejected'):
            self.rotation.promote(NEW, SHA, self.restore)
        self.assertEqual(self.j.read(), before)
        self.assertEqual(self.fake.patches, patches)
        self.assertEqual(self.fake.objects[PARENT]['appProperties']['health_r_state'], 'PROMOTED')
        self.assertTrue(self.fake.objects[OLD]['trashed'])

    def test_promoted_done_legacy_v1_without_zip_binding_fails_closed(self):
        self.promoted_done()
        props=self.fake.objects[PARENT]['appProperties']
        props.pop('health_r_old_zip')
        props['health_r_v']='1'
        before=dict(props)
        patches=list(self.fake.patches)
        with self.assertRaisesRegex(RotationStop,'cloud_journal_old_zip_id_binding_required'):
            self.rotation.promote(NEW,SHA,self.restore)
        self.assertEqual(props,before)
        self.assertEqual(self.fake.patches,patches)
        self.assertTrue(self.fake.objects[OLD]['trashed'])

    def test_promoted_done_rejects_renamed_physical_zip(self):
        self.promoted_done()
        self.fake.objects[OLD + 'file']['name'] = 'unexpected.zip'
        before = list(self.fake.patches)
        with self.assertRaisesRegex(RotationStop, 'complete_set_physical_archive_identity_rejected'):
            self.rotation.promote(NEW, SHA, self.restore)
        self.assertEqual(self.j.read()['state'], 'PROMOTED')
        self.assertEqual(self.fake.patches, before)

    def test_promoted_done_rejects_old_acl_drift_without_patch(self):
        self.promoted_done()
        self.fake.objects[OLD]['permissions'].append({'type':'anyone','role':'reader'})
        before = list(self.fake.patches)
        with self.assertRaisesRegex(RotationStop, 'private_backup_owner_acl_required'):
            self.rotation.promote(NEW, SHA, self.restore)
        self.assertEqual(self.j.read()['state'], 'PROMOTED')
        self.assertEqual(self.fake.patches, before)

    def test_promoted_done_rejects_old_state_drift_without_patch(self):
        self.promoted_done()
        self.fake.objects[OLD]['appProperties']['health_recovery_state'] = 'CANDIDATE'
        before = list(self.fake.patches)
        with self.assertRaisesRegex(RotationStop, 'completed_rotation_old_state_changed'):
            self.rotation.promote(NEW, SHA, self.restore)
        self.assertEqual(self.j.read()['state'], 'PROMOTED')
        self.assertEqual(self.fake.patches, before)

    def test_promoted_done_rejects_old_untrash_without_patch(self):
        self.promoted_done()
        self.fake.objects[OLD]['trashed'] = False
        before = list(self.fake.patches)
        with self.assertRaisesRegex(RotationStop, 'completed_rotation_old_not_trashed'):
            self.rotation.promote(NEW, SHA, self.restore)
        self.assertEqual(self.j.read()['state'], 'PROMOTED')
        self.assertEqual(self.fake.patches, before)

    def test_promoted_done_rejects_target_downgrade_without_patch(self):
        self.promoted_done()
        self.fake.objects[NEW]['appProperties']['health_recovery_state'] = 'CANDIDATE'
        before = list(self.fake.patches)
        with self.assertRaisesRegex(RotationStop, 'promoted_rotation_target_not_active'):
            self.rotation.promote(NEW, SHA, self.restore)
        self.assertEqual(self.j.read()['state'], 'PROMOTED')
        self.assertEqual(self.fake.patches, before)



if __name__ == '__main__':
    unittest.main()
