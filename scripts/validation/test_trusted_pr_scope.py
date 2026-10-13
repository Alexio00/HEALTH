"""Nonsecret negative fixtures for trusted scope; never calls GitHub."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from trusted_pr_scope import check_scope, ScopeStop

HEAD = "a" * 40
OWNER = 308028794


def scenario(filename, mode="pwa", status="modified", previous=None, reg="100644"):
    head = {filename: ("blob", reg)}
    base = {previous or filename: ("blob", "100644")}
    row = dict(filename=filename, status=status)
    if previous:
        row["previous_filename"] = previous
    return [row], head, base


def verify(filename, mode="pwa", author=22, body="", status="modified", previous=None, reg="100644"):
    items, head, base = scenario(filename, mode, status, previous, reg)
    return check_scope(items, mode, author, body, HEAD, head, base)


class ScopeFixtures(unittest.TestCase):
    def test_valid_pwa_frontend_only(self):
        for path in ("frontend/app.js", "frontend/tests/scope.mjs", "AGENTS.md", "docs/PWA_RELEASE.md"):
            with self.subTest(path=path):
                self.assertEqual(verify(path)["scope"], "pwa")

    def test_valid_scheduler_only(self):
        for path in ("scripts/scheduler/complete_pipeline.py", "scripts/automation/health_activity.mjs",
                     "scripts/automation/supabase_keepalive.py", "docs/SCHEDULER_CONSOLIDATION_RU.md"):
            with self.subTest(path=path):
                self.assertEqual(verify(path, "scheduler-code")["scope"], "scheduler-code")

    def test_backend_and_secret_paths_rejected(self):
        for mode in ("pwa", "scheduler-code"):
            for path in ("scripts/writer/policy.py", "db/migration.sql", "supabase/config.ts",
                         "frontend/private/config.json", "frontend/.env", "sources/medical.pdf",
                         ".github/workflows/other.yml", "scripts/scheduler/x.sql"):
                with self.subTest(mode=mode, path=path), self.assertRaises(ScopeStop):
                    verify(path, mode)

    def test_control_requires_owner_and_current_head(self):
        for path, mode, prefix in (
            (".github/workflows/code-validation.yml", "pwa", "PWA-RELEASE-CONTROL: "),
            ("frontend/release/scope.mjs", "pwa", "PWA-RELEASE-CONTROL: "),
            (".github/workflows/health-scheduler-validation.yml", "scheduler-code", "SCHEDULER-CONTROL: "),
        ):
            with self.subTest(path=path):
                with self.assertRaises(ScopeStop):
                    verify(path, mode, OWNER, prefix + "b"*40)
                with self.assertRaises(ScopeStop):
                    verify(path, mode, 21, prefix + HEAD)
                self.assertEqual(verify(path, mode, OWNER, prefix + HEAD)["control_paths"], 1)

    def test_head_symlink_and_mode_fail_closed(self):
        for mode, path in (("pwa", "frontend/app.js"), ("scheduler-code", "scripts/scheduler/x.py")):
            with self.assertRaisesRegex(ScopeStop, "nonregular"):
                verify(path, mode, reg="120000")

    def test_renames_check_old_and_new_paths(self):
        with self.assertRaises(ScopeStop):
            verify("frontend/app.js", "pwa", status="renamed", previous="scripts/writer/owner.py")
        with self.assertRaises(ScopeStop):
            verify("scripts/writer/owner.py", "pwa", status="renamed", previous="frontend/app.js")
        result = verify("frontend/renamed.js", status="renamed", previous="frontend/old.js")
        self.assertEqual(result["checked_files"], 1)

    def test_deleted_file_and_missing_head(self):
        row, head, base = scenario("frontend/old.js", status="removed")
        self.assertEqual(check_scope(row, "pwa", 1, "", HEAD, {}, base)["checked_files"], 1)
        with self.assertRaises(ScopeStop):
            check_scope(row, "pwa", 1, "", HEAD, head, {})
        with self.assertRaises(ScopeStop):
            check_scope(*scenario("frontend/app.js")[:1], "pwa", 1, "", HEAD, {}, {})

    def test_spoofed_job_not_trusted_as_policy(self):
        # A PR-controlled job with the same name cannot change this policy's
        # own verdict: the workflow must be protected and independently run.
        with self.assertRaises(ScopeStop):
            verify(".github/workflows/health-trusted-scope.yml")
        with self.assertRaises(ScopeStop):
            verify(".github/workflows/health-trusted-scope.yml", "scheduler-code")

    def test_duplicate_and_unsafe_segments(self):
        items, ht, bt = scenario("frontend/app.js")
        with self.assertRaises(ScopeStop):
            check_scope(items + items, "pwa", 1, "", HEAD, ht, bt)
        for path in ("frontend/../db/x", "frontend//x", "frontend/.hidden/x", "frontend/secrets/a.json"):
            with self.assertRaises(ScopeStop):
                verify(path)


if __name__ == "__main__":
    unittest.main()
