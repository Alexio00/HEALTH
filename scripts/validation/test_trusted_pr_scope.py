"""Nonsecret negative fixtures for trusted scope; never calls GitHub."""
import sys
import unittest
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from trusted_pr_scope import check_scope, check_trusted_policy_release, ScopeStop

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

    def test_independent_policy_pin_survives_unrelated_main_update(self):
        old_accepted = "a" * 40
        moved_main = "c" * 40
        original_workflow_blob = "d" * 40
        metadata = {"type": "file",
                    "path": ".github/workflows/health-trusted-scope.yml",
                    "sha": original_workflow_blob, "size": 999}
        with patch("trusted_pr_scope.api", return_value=metadata) as fetch:
            self.assertTrue(check_trusted_policy_release(
                old_accepted, old_accepted, moved_main,
                original_workflow_blob, "synthetic-readonly-token"))
            self.assertEqual(fetch.call_count, 1)
            self.assertIn("?ref=" + moved_main, fetch.call_args.args[0])

    def test_independent_policy_pin_rejects_malformed_unaccepted_code(self):
        token = "synthetic-readonly-token"
        with patch("trusted_pr_scope.api") as fetch:
            for args in ((None, "a" * 40, "b" * 40, "c" * 40, token),
                         ("a" * 40, "e" * 40, "b" * 40, "c" * 40, token),
                         ("a" * 40, "a" * 40, None, "c" * 40, token),
                         ("a" * 40, "a" * 40, "b" * 40, "", token)):
                with self.subTest(args=args), self.assertRaisesRegex(
                        ScopeStop, "independent_policy_pin_required"):
                    check_trusted_policy_release(*args)
            fetch.assert_not_called()

    def test_independent_policy_pin_rejects_changed_workflow_and_invalid_metadata(self):
        pin = "a" * 40
        for metadata in ({"type": "file",
                          "path": ".github/workflows/health-trusted-scope.yml",
                          "sha": "b" * 40, "size": 100},
                         {"type": "dir", "path": ".github/workflows/health-trusted-scope.yml",
                          "sha": "c" * 40, "size": 100},
                         {"type": "file", "path": ".github/workflows/other.yml",
                          "sha": "c" * 40, "size": 100},
                         {"type": "file",
                          "path": ".github/workflows/health-trusted-scope.yml",
                          "sha": "c" * 40, "size": 0}):
            with self.subTest(metadata=metadata), patch(
                    "trusted_pr_scope.api", return_value=metadata):
                with self.assertRaisesRegex(
                        ScopeStop, "trusted_default_workflow_blob_changed"):
                    check_trusted_policy_release(pin, pin, "b" * 40,
                                                 "c" * 40, "synthetic-token")

    def test_writer_branch_bounded_code_requires_owner_exact_sha(self):
        candidates = ("scripts/writer/gateway_contract.py",
                      "scripts/writer/standby_runtime.sql",
                      "scripts/validation/security_invariants.sql",
                      "db/migrations/core.sql",
                      "supabase/migrations/20261014_view.sql",
                      "docs/WRITER_RELEASE.md",
                      ".github/workflows/code-validation.yml")
        for path in candidates:
            with self.subTest(path=path):
                with self.assertRaisesRegex(ScopeStop, "control_changes_require_owner_exact_head"):
                    verify(path, "writer-code")
                with self.assertRaisesRegex(ScopeStop, "control_changes_require_owner_exact_head"):
                    verify(path, "writer-code", OWNER, "WRITER-CONTROL: " + "b" * 40)
                self.assertEqual(
                    verify(path, "writer-code", OWNER,
                           "WRITER-CONTROL: " + HEAD)["scope"], "writer-code")

    def test_writer_branch_cannot_modify_trusted_issuer_or_other_trains(self):
        for path in (".github/workflows/writer-authorization.yml",
                     ".github/workflows/health-trusted-scope.yml",
                     ".github/workflows/deploy-pages.yml", "frontend/app.js",
                     "scripts/scheduler/complete_archive.py", "AGENTS.md",
                     "docs/PROJECT_STATE.md", "secrets/file.pem",
                     "scripts/writer/.env", "scripts/writer/pin.key"):
            with self.subTest(path=path), self.assertRaises(ScopeStop):
                verify(path, "writer-code", OWNER, "WRITER-CONTROL: " + HEAD)

    def test_writer_branch_renames_symlinks_and_deleted_head_fail_closed(self):
        with self.assertRaises(ScopeStop):
            verify("scripts/writer/x.py", "writer-code", OWNER,
                   "WRITER-CONTROL: " + HEAD, status="renamed",
                   previous=".github/workflows/writer-authorization.yml")
        with self.assertRaisesRegex(ScopeStop, "nonregular"):
            verify("scripts/writer/gateway_contract.py", "writer-code", OWNER,
                   "WRITER-CONTROL: " + HEAD, reg="120000")
        with self.assertRaisesRegex(ScopeStop, "control_changes_require_owner_exact_head"):
            verify("scripts/writer/removed.py", "writer-code", status="removed")

    def test_duplicate_and_unsafe_segments(self):
        items, ht, bt = scenario("frontend/app.js")
        with self.assertRaises(ScopeStop):
            check_scope(items + items, "pwa", 1, "", HEAD, ht, bt)
        for path in ("frontend/../db/x", "frontend//x", "frontend/.hidden/x", "frontend/secrets/a.json"):
            with self.assertRaises(ScopeStop):
                verify(path)


if __name__ == "__main__":
    unittest.main()
