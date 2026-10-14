"""B-02/H-04 fail-closed synthetic recovery; no production API or patient data."""
import copy
import json
import unittest
from unittest.mock import patch

from complete_cloud import CompleteCloud
from complete_pipeline import choose_existing, complete_activation_marker, SourceStop

PARENT="syntheticparent123"
NEW="syntheticnew123"
OLD="syntheticold123"
SHA="a"*64
EXEC="e"*64
PRODUCER="b"*40
NAME="complete-20261012T000000Z-abcd1234"


def meta(id, state="CANDIDATE", producer=PRODUCER, sha=SHA):
    return dict(id=id, name=NAME, parents=[PARENT],
        mimeType="application/vnd.google-apps.folder", trashed=False,
        appProperties=dict(health_complete_set="v1",
           health_recovery_state=state,health_archive_sha256=sha,
           health_pipeline_commit=producer,health_archive_bytes="20"))


class FakeTransport:
    def __init__(self, objects):
        self.objects=objects
        self.patch_count=0
        self.lose_marker=None
        self.lose_candidate=None

    def request(self, path, method="GET", body=None, **unused):
        id=path.split("/")[4].split("?")[0]
        if method=="PATCH":
            self.patch_count+=1
            if id==PARENT and self.lose_marker=="before":
                raise RuntimeError("lost_before_marker")
            if id==NEW and self.lose_candidate=="before":
                raise RuntimeError("lost_before_candidate")
            patch=json.loads(body)
            self.objects[id].setdefault("appProperties",{}).update(patch["appProperties"])
            if id==PARENT and self.lose_marker=="after":
                raise RuntimeError("lost_after_marker")
            if id==NEW and self.lose_candidate=="after":
                raise RuntimeError("lost_after_candidate")
        return copy.deepcopy(self.objects[id])


class FakeCloud:
    def __init__(self,state="CANDIDATE"):
        self.parent=PARENT
        self.items={PARENT:{"id":PARENT,"appProperties":{}},
                    NEW:meta(NEW,state),
                    OLD:meta(OLD,"ACTIVE",producer="c"*40,sha="d"*64)}
        self.t=FakeTransport(self.items)
        self.files_verified=False
    def meta(self,id):return copy.deepcopy(self.items[id])
    def children(self,id):
        if id==NEW:
            if self.files_verified:
                return [dict(id="syntheticfile123",name="complete-recovery.zip",
                    sha256Checksum=SHA,size="20")]
            return []
        return [self.meta(k) for k in self.items if k!=PARENT and self.items[k].get("trashed") is False]
    def quarantine_incomplete_upload(self,folder,sha,producer,journal):
        stub=object.__new__(CompleteCloud)
        stub.parent=self.parent
        stub.meta=self.meta
        stub.children=self.children
        stub.t=self.t
        return CompleteCloud.quarantine_incomplete_upload(stub,folder,sha,producer,journal)
    def finish_upload(self,m,producer):
        # Integrate the actual CompleteCloud method with a simulated SHA-verified download.
        stub=object.__new__(CompleteCloud)
        stub.parent=self.parent
        stub.meta=self.meta
        stub.t=self.t
        def readback(id,sha,label,allow_uploading=False):
            if not self.files_verified:raise SourceStop("candidate_remote_archive_rejected")
            if not allow_uploading or sha!=SHA or id!=NEW:raise SourceStop("unexpected_download")
        stub.download=readback
        return CompleteCloud.finish_upload(stub,m,producer)


class FakeJournal:
    def __init__(self,state="DONE",sha=SHA,target=NEW):
        self.row=dict(state=state,sha=sha,target=target)
    def read(self):return copy.deepcopy(self.row)


def verified():
    return dict(status="ACTUAL_COMPLETE_SET_RESTORE_PASS",archive_sha256=SHA,
        all_members_verified=True,database_restore_pass=True,auth_http_pass=True,
        source_rebind_pass=True)


class ReconciliationTests(unittest.TestCase):
    def test_failed_upload_does_not_create_candidate_or_rotate_old(self):
        cloud=FakeCloud("UPLOADING");journal=FakeJournal()
        with self.assertRaisesRegex(SourceStop,"candidate_remote_archive_rejected"):
            choose_existing("candidate",cloud,journal,PRODUCER,SHA)
        self.assertEqual(cloud.items[NEW]["appProperties"]["health_recovery_state"],"UPLOADING")
        self.assertEqual(cloud.items[OLD]["appProperties"]["health_recovery_state"],"ACTIVE")
        self.assertEqual(cloud.t.patch_count,0)

    def test_complete_orphan_reconciles_exact_remote_archive(self):
        cloud=FakeCloud("UPLOADING");cloud.files_verified=True
        self.assertEqual(choose_existing("candidate",cloud,FakeJournal(),PRODUCER,SHA),(NEW,SHA,False))
        self.assertEqual(cloud.items[NEW]["appProperties"]["health_recovery_state"],"CANDIDATE")

    def test_lost_response_candidate_marker_after_remote_apply(self):
        cloud=FakeCloud("UPLOADING");cloud.files_verified=True;cloud.t.lose_candidate="after"
        self.assertEqual(choose_existing("candidate",cloud,FakeJournal(),PRODUCER,SHA),(NEW,SHA,False))
        self.assertEqual(cloud.t.patch_count,1)

    def test_lost_response_before_candidate_patch_is_retryable(self):
        cloud=FakeCloud("UPLOADING");cloud.files_verified=True;cloud.t.lose_candidate="before"
        with self.assertRaisesRegex(RuntimeError,"lost_before_candidate"):
            choose_existing("candidate",cloud,FakeJournal(),PRODUCER,SHA)
        self.assertEqual(cloud.items[NEW]["appProperties"]["health_recovery_state"],"UPLOADING")
        cloud.t.lose_candidate=None
        self.assertEqual(choose_existing("candidate",cloud,FakeJournal(),PRODUCER,SHA),(NEW,SHA,False))

    def test_foreign_or_ambiguous_orphan_stops(self):
        cloud=FakeCloud("UPLOADING");cloud.files_verified=True
        cloud.items[NEW]["appProperties"]["health_pipeline_commit"]="c"*40
        with self.assertRaises(SourceStop):choose_existing("candidate",cloud,FakeJournal(),PRODUCER,SHA)
        cloud.items[NEW]["appProperties"]["health_pipeline_commit"]=PRODUCER
        cloud.items["extra_folder"]=meta("extra_folder","CANDIDATE")
        with self.assertRaisesRegex(SourceStop,"conflicting_candidates"):
            choose_existing("candidate",cloud,FakeJournal(),PRODUCER,SHA)

    def test_incomplete_daily_quarantine_then_next_daily_can_capture(self):
        cloud=FakeCloud("UPLOADING");journal=FakeJournal()
        with self.assertRaisesRegex(SourceStop,"candidate_remote_archive_rejected"):
            choose_existing("daily",cloud,journal,PRODUCER,SHA)
        self.assertEqual(cloud.t.patch_count,0)
        self.assertEqual(cloud.items[OLD]["appProperties"]["health_recovery_state"],"ACTIVE")
        status=cloud.quarantine_incomplete_upload(NEW,SHA,PRODUCER,journal)
        self.assertEqual(status["status"],"INCOMPLETE_UPLOADING_QUARANTINED")
        self.assertEqual(cloud.items[NEW]["appProperties"]["health_recovery_state"],"ABANDONED")
        self.assertEqual(cloud.items[OLD]["appProperties"]["health_recovery_state"],"ACTIVE")
        self.assertEqual(choose_existing("daily",cloud,journal,PRODUCER,SHA),None)
        # Next daily can now create an independent new candidate.
        cloud.items["syntheticfreshfolder123"]=meta("syntheticfreshfolder123","CANDIDATE")
        self.assertEqual(choose_existing("daily",cloud,journal,PRODUCER,SHA),
                         ("syntheticfreshfolder123",SHA,False))
        self.assertEqual(cloud.items[OLD]["appProperties"]["health_recovery_state"],"ACTIVE")

    def test_full_upload_accepted_during_daily_no_quarantine(self):
        cloud=FakeCloud("UPLOADING");cloud.files_verified=True
        self.assertEqual(choose_existing("daily",cloud,FakeJournal(),PRODUCER,SHA),(NEW,SHA,False))
        self.assertEqual(cloud.items[NEW]["appProperties"]["health_recovery_state"],"CANDIDATE")
        with self.assertRaises(SourceStop):
            cloud.quarantine_incomplete_upload(NEW,SHA,PRODUCER,FakeJournal())

    def test_complete_remote_upload_not_marked_abandoned(self):
        cloud=FakeCloud("UPLOADING");cloud.files_verified=True
        with self.assertRaisesRegex(SourceStop,"complete_metadata_requires_resume"):
            cloud.quarantine_incomplete_upload(NEW,SHA,PRODUCER,FakeJournal())
        self.assertEqual(cloud.t.patch_count,0)

    def test_quarantine_rejects_wrong_identity_digest_pending_and_second_candidate(self):
        for sha,producer in [("c"*64,PRODUCER),(SHA,"c"*40)]:
            cloud=FakeCloud("UPLOADING")
            with self.assertRaises(SourceStop):
                cloud.quarantine_incomplete_upload(NEW,sha,producer,FakeJournal())
            self.assertEqual(cloud.t.patch_count,0)
        cloud=FakeCloud("UPLOADING")
        with self.assertRaisesRegex(SourceStop,"pending_rotation"):
            cloud.quarantine_incomplete_upload(NEW,SHA,PRODUCER,FakeJournal("PROMOTED"))
        self.assertEqual(cloud.t.patch_count,0)
        cloud=FakeCloud("UPLOADING")
        cloud.items["anothercandidate123"]=meta("anothercandidate123","CANDIDATE")
        with self.assertRaisesRegex(SourceStop,"one_upload_one_active"):
            cloud.quarantine_incomplete_upload(NEW,SHA,PRODUCER,FakeJournal())
        self.assertEqual(cloud.t.patch_count,0)

    def test_quarantine_lost_patch_response_readback(self):
        for loss in ("before","after"):
            cloud=FakeCloud("UPLOADING")
            cloud.t.lose_candidate=loss
            if loss=="before":
                with self.assertRaisesRegex(RuntimeError,"lost_before_candidate"):
                    cloud.quarantine_incomplete_upload(NEW,SHA,PRODUCER,FakeJournal())
                self.assertEqual(cloud.items[NEW]["appProperties"]["health_recovery_state"],"UPLOADING")
                cloud.t.lose_candidate=None
                self.assertEqual(cloud.quarantine_incomplete_upload(NEW,SHA,PRODUCER,FakeJournal())["permanent_deletes"],0)
            else:
                self.assertEqual(cloud.quarantine_incomplete_upload(NEW,SHA,PRODUCER,FakeJournal())["permanent_deletes"],0)
            self.assertEqual(cloud.items[NEW]["appProperties"]["health_recovery_state"],"ABANDONED")
            self.assertEqual(cloud.items[OLD]["appProperties"]["health_recovery_state"],"ACTIVE")

    def test_activate_does_not_pick_unfinished_upload(self):
        cloud=FakeCloud("UPLOADING");cloud.files_verified=True
        with self.assertRaisesRegex(SourceStop,"unfinished_upload"):
            choose_existing("activate",cloud,FakeJournal(),PRODUCER,SHA)

    def test_activation_resumes_same_done_active(self):
        cloud=FakeCloud("ACTIVE")
        cloud.items[OLD]["trashed"]=True
        j=FakeJournal()
        self.assertEqual(choose_existing("activate",cloud,j,PRODUCER,SHA),(NEW,SHA,True))
        self.assertTrue(complete_activation_marker(cloud,j,NEW,SHA,PRODUCER,EXEC,verified()))
        self.assertEqual(cloud.items[PARENT]["appProperties"]["health_full_restore_archive"],SHA)
        self.assertEqual(cloud.t.patch_count,1)
        self.assertTrue(complete_activation_marker(cloud,j,NEW,SHA,PRODUCER,EXEC,verified()))
        self.assertEqual(cloud.t.patch_count,1)

    def test_lost_marker_response_after_apply_is_successful(self):
        cloud=FakeCloud("ACTIVE");cloud.items[OLD]["trashed"]=True
        cloud.t.lose_marker="after"
        self.assertTrue(complete_activation_marker(cloud,FakeJournal(),NEW,SHA,PRODUCER,EXEC,verified()))

    def test_lost_marker_response_before_apply_retries_exactly(self):
        cloud=FakeCloud("ACTIVE");cloud.items[OLD]["trashed"]=True;cloud.t.lose_marker="before"
        with self.assertRaisesRegex(RuntimeError,"lost_before_marker"):
            complete_activation_marker(cloud,FakeJournal(),NEW,SHA,PRODUCER,EXEC,verified())
        self.assertEqual(cloud.items[PARENT]["appProperties"],{})
        cloud.t.lose_marker=None
        self.assertTrue(complete_activation_marker(cloud,FakeJournal(),NEW,SHA,PRODUCER,EXEC,verified()))

    def test_no_marker_with_invalid_restore_or_unfinished_journal(self):
        for bad in [dict(verified(),source_rebind_pass=False),
                    dict(verified(),archive_sha256="c"*64),
                    dict(verified(),status="FAKE_PASS")]:
            cloud=FakeCloud("ACTIVE");cloud.items[OLD]["trashed"]=True
            with self.subTest(bad=bad),self.assertRaises(SourceStop):
                complete_activation_marker(cloud,FakeJournal(),NEW,SHA,PRODUCER,EXEC,bad)
            self.assertEqual(cloud.t.patch_count,0)
        cloud=FakeCloud("ACTIVE");cloud.items[OLD]["trashed"]=True
        with self.assertRaises(SourceStop):
            complete_activation_marker(cloud,FakeJournal("PROMOTED"),NEW,SHA,PRODUCER,EXEC,verified())

    def test_ambiguous_active_or_wrong_digest_fails(self):
        cloud=FakeCloud("ACTIVE")
        with self.assertRaisesRegex(SourceStop,"unique_verified_active"):
            complete_activation_marker(cloud,FakeJournal(),NEW,SHA,PRODUCER,EXEC,verified())
        cloud.items[OLD]["trashed"]=True
        with self.assertRaises(SourceStop):
            choose_existing("activate",cloud,FakeJournal(),PRODUCER,"f"*64)
        with self.assertRaises(SourceStop):
            complete_activation_marker(cloud,FakeJournal(sha="f"*64),NEW,SHA,PRODUCER,EXEC,verified())


if __name__=="__main__":unittest.main()
