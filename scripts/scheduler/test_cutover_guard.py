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
            ("HEALTH_RELEASE_CANDIDATE_SHA256", "bad"),
        ]:
            with self.subTest(field=key, value=invalid):
                bad = self.valid()
                bad[key] = invalid
                with self.assertRaises(CutoverStop):
                    require_release_context(bad, "candidate", self.PIN)
                del bad[key]
                with self.assertRaises(CutoverStop):
                    require_release_context(bad, "candidate", self.PIN)

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
