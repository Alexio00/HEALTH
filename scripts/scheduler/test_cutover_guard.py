"""Only synthetic release-gate cases; never touches production resources."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cutover_guard import ACK, WORKFLOW, CutoverStop, require_release_context


class CutoverGuardTests(unittest.TestCase):
    PIN = "a" * 40
    MAIN = "b" * 40

    def valid(self, mode="candidate"):
        return dict(
            GITHUB_ACTIONS="true", GITHUB_REPOSITORY="Alexio00/HEALTH",
            GITHUB_REF="refs/heads/main", GITHUB_EVENT_NAME="workflow_dispatch",
            GITHUB_ACTOR_ID="308028794", GITHUB_WORKFLOW_REF=WORKFLOW,
            GITHUB_RUN_ATTEMPT="1", GITHUB_TRIGGERING_ACTOR="trusted-owner",
            GITHUB_SHA=self.MAIN, HEALTH_RELEASE_MAIN_ACCEPTED_SHA=self.MAIN,
            HEALTH_COMPLETE_SERIALIZED="1", HEALTH_INREPO_RELEASE_ENABLED="true",
            HEALTH_LEGACY_BACKUP_PAUSED="true",
            HEALTH_INREPO_BACKUP_ENABLED="false",
            HEALTH_RELEASE_ACK=ACK, HEALTH_RELEASE_MODE=mode,
            HEALTH_BACKUP_EXECUTOR_SHA=self.PIN,
            HEALTH_BACKUP_PRODUCER_SHA=self.PIN,
            HEALTH_RELEASE_EXPECTED_SHA=self.PIN,
            HEALTH_RELEASE_CANDIDATE_SHA256="c" * 64,
        )

    def test_candidate_and_activation_explicitly_permitted(self):
        for mode in ("candidate", "activate"):
            with self.subTest(mode=mode):
                self.assertTrue(require_release_context(self.valid(mode), mode, self.PIN))
        with patch("cutover_guard.subprocess.check_output", return_value=self.PIN + "\n"):
            self.assertTrue(require_release_context(self.valid(), "candidate"))

    def test_missing_or_wrong_gate_fails_closed(self):
        for key, invalid in [
            ("GITHUB_ACTIONS", "false"),
            ("GITHUB_REPOSITORY", "another/repo"),
            ("GITHUB_REF", "refs/heads/scheduler-code"),
            ("GITHUB_EVENT_NAME", "schedule"),
            ("GITHUB_EVENT_NAME", "pull_request"),
            ("GITHUB_ACTOR_ID", "123"),
            ("GITHUB_WORKFLOW_REF", "Alexio00/HEALTH/.github/workflows/evil.yml@refs/heads/main"),
            ("GITHUB_RUN_ATTEMPT", "2"),
            ("HEALTH_COMPLETE_SERIALIZED", "0"),
            ("HEALTH_INREPO_RELEASE_ENABLED", "false"),
            ("HEALTH_LEGACY_BACKUP_PAUSED", "false"),
            ("HEALTH_INREPO_BACKUP_ENABLED", "true"),
            ("HEALTH_RELEASE_ACK", "I agree"),
            ("HEALTH_RELEASE_MODE", "daily"),
            ("HEALTH_RELEASE_MAIN_ACCEPTED_SHA", self.PIN),
            ("GITHUB_SHA", self.PIN),
            ("HEALTH_BACKUP_EXECUTOR_SHA", self.MAIN),
            ("HEALTH_BACKUP_PRODUCER_SHA", self.MAIN),
            ("HEALTH_RELEASE_EXPECTED_SHA", self.MAIN),
        ]:
            with self.subTest(field=key, value=invalid):
                bad = self.valid()
                bad[key] = invalid
                with self.assertRaises(CutoverStop):
                    require_release_context(bad, "candidate", self.PIN)
                del bad[key]
                with self.assertRaises(CutoverStop):
                    require_release_context(bad, "candidate", self.PIN)

    def test_replayed_owner_dispatch_with_different_triggering_actor_is_rejected(self):
        # GitHub keeps GITHUB_ACTOR_ID, SHA, ref, and original inputs on re-run.
        # Only GITHUB_RUN_ATTEMPT reliably distinguishes this attempt.
        for mode in ("candidate", "activate", "quarantine-orphan"):
            initial = self.valid(mode)
            if mode == "quarantine-orphan":
                initial.update(
                    HEALTH_ORPHAN_ACK="ABANDON_INCOMPLETE_UPLOADING_ONLY",
                    HEALTH_ORPHAN_FOLDER_ID="syntheticfolder123",
                )
            with self.subTest(mode=mode, attempt="first"):
                self.assertTrue(require_release_context(initial, mode, self.PIN))
            replay = dict(initial, GITHUB_RUN_ATTEMPT="2",
                          GITHUB_TRIGGERING_ACTOR="different-rerun-user")
            with self.subTest(mode=mode, attempt="second"), self.assertRaisesRegex(
                CutoverStop, "release_rerun_or_missing_attempt_rejected"
            ):
                require_release_context(replay, mode, self.PIN)

    def test_missing_noncanonical_or_incremented_attempt_fails_closed(self):
        for attempt in (None, "", "0", "01", "2", "3", "bogus"):
            env = self.valid()
            if attempt is None:
                del env["GITHUB_RUN_ATTEMPT"]
            else:
                env["GITHUB_RUN_ATTEMPT"] = attempt
            with self.subTest(attempt=attempt), self.assertRaisesRegex(
                CutoverStop, "release_rerun_or_missing_attempt_rejected"
            ):
                require_release_context(env, "candidate", self.PIN)

    def test_quarantine_is_owner_only_and_exact(self):
        good=self.valid("quarantine-orphan")
        good.update(HEALTH_ORPHAN_ACK="ABANDON_INCOMPLETE_UPLOADING_ONLY",
                    HEALTH_ORPHAN_FOLDER_ID="syntheticfolder123",
                    HEALTH_INREPO_BACKUP_ENABLED="true")
        self.assertTrue(require_release_context(good,"quarantine-orphan",self.PIN))
        for key,value in [("HEALTH_ORPHAN_FOLDER_ID",""),
                          ("HEALTH_ORPHAN_ACK","missing"),
                          ("HEALTH_RELEASE_CANDIDATE_SHA256","invalid"),
                          ("GITHUB_ACTOR_ID","1234")]:
            bad=dict(good);bad[key]=value
            with self.subTest(key=key), self.assertRaises(CutoverStop):
                require_release_context(bad,"quarantine-orphan",self.PIN)
        for mode in ("candidate","activate"):
            bad=self.valid(mode);bad["HEALTH_INREPO_BACKUP_ENABLED"]="true"
            with self.assertRaises(CutoverStop):
                require_release_context(bad,mode,self.PIN)

    def test_checkout_and_mode_are_bound(self):
        with self.assertRaises(CutoverStop):
            require_release_context(self.valid(), "activate", self.PIN)
        with self.assertRaises(CutoverStop):
            require_release_context({**self.valid("activate"), "HEALTH_RELEASE_CANDIDATE_SHA256": "wrong"}, "activate", self.PIN)
        with self.assertRaises(CutoverStop):
            require_release_context(self.valid(), "daily", self.PIN)
        with self.assertRaises(CutoverStop):
            require_release_context(self.valid(), "candidate", self.MAIN)
        with patch("cutover_guard.subprocess.check_output", side_effect=OSError):
            with self.assertRaises(CutoverStop):
                require_release_context(self.valid(), "candidate")

    def test_release_does_not_assert_legacy_pause_is_automatically_verified(self):
        source = (Path(__file__).with_name("cutover_guard.py")).read_text()
        self.assertIn("not evidence that another repository", source)
        self.assertIn("owner must", source.lower())


if __name__ == "__main__":
    unittest.main()
