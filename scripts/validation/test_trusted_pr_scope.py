"""Nonsecret negative fixtures for trusted scope; never calls GitHub."""
import sys
import unittest
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from trusted_pr_scope import (check_scope, check_trusted_policy_release,
                              check_event, git_tree, ScopeStop)

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

    def test_component_pr_cannot_modify_ci_workflows_even_with_owner_marker(self):
        for mode, path, marker in (
            ('pwa', '.github/workflows/code-validation.yml', 'PWA-RELEASE-CONTROL: '),
            ('pwa', '.github/workflows/deploy-pages.yml', 'PWA-RELEASE-CONTROL: '),
            ('scheduler-code', '.github/workflows/health-scheduler-validation.yml', 'SCHEDULER-CONTROL: '),
            ('writer-code', '.github/workflows/code-validation.yml', 'WRITER-CONTROL: '),
            ('pwa', 'frontend/release/check.mjs', 'PWA-RELEASE-CONTROL: ')):
            with self.subTest(mode=mode, path=path), self.assertRaises(ScopeStop):
                verify(path, mode, OWNER, marker + HEAD)

    def test_nested_sensitive_auth_paths_rejected(self):
        for path in ('frontend/oauth-test/consent.mjs', 'frontend/credentials/reader.js',
                     'frontend/config/auth-bridge.js', 'frontend/tokens/preview.json',
                     'frontend/supabase-client.js', 'frontend/secret-list.json'):
            with self.subTest(path=path), self.assertRaises(ScopeStop):
                verify(path, 'pwa', OWNER, 'PWA-RELEASE-CONTROL: ' + HEAD)

    def test_writer_cannot_modify_trusted_security_policy(self):
        for path in ('scripts/validation/trusted_pr_scope.py',
                     'scripts/validation/test_trusted_pr_scope.py',
                     'scripts/validation/public_secret_guard.py'):
            with self.subTest(path=path), self.assertRaises(ScopeStop):
                verify(path, 'writer-code', OWNER, 'WRITER-CONTROL: ' + HEAD)

    def test_head_symlink_and_mode_fail_closed(self):
        for mode, path in (("pwa", "frontend/app.js"), ("scheduler-code", "scripts/scheduler/x.py")):
            with self.assertRaisesRegex(ScopeStop, "tree_state_invalid"):
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
                      "docs/WRITER_RELEASE.md")
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
        for path in (".github/workflows/code-validation.yml",
                     ".github/workflows/writer-authorization.yml",
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
        with self.assertRaisesRegex(ScopeStop, "tree_state_invalid"):
            verify("scripts/writer/gateway_contract.py", "writer-code", OWNER,
                   "WRITER-CONTROL: " + HEAD, reg="120000")
        # A deletion must be absent in HEAD and present only in the base tree.
        entry = {"filename": "scripts/writer/removed.py", "status": "removed"}
        base = {entry["filename"]: ("blob", "100644")}
        with self.assertRaisesRegex(ScopeStop, "control_changes_require_owner_exact_head"):
            check_scope([entry], "writer-code", OWNER, "", HEAD, {}, base)
        self.assertEqual(
            check_scope([entry], "writer-code", OWNER,
                        "WRITER-CONTROL: " + HEAD, HEAD, {}, base)["scope"],
            "writer-code")

    def test_git_tree_rejects_duplicate_and_malformed_metadata(self):
        base = {'tree': {'sha': HEAD}}
        entry = {'path': 'frontend/app.js', 'type': 'blob', 'mode': '100644', 'sha': HEAD}
        responses = (
            {'truncated': False, 'tree': [entry, dict(entry)]},
            {'tree': [entry]},
            {'truncated': True, 'tree': [entry]},
            {'truncated': False, 'tree': [{**entry, 'mode': 'unknown'}]},
            {'truncated': False, 'tree': [{**entry, 'sha': None}]},
        )
        for response in responses:
            with self.subTest(response=response), patch('trusted_pr_scope.api',
                side_effect=[base, response]):
                with self.assertRaises(ScopeStop):
                    git_tree('synthetic-readonly-token', HEAD)

    def test_final_pr_snapshot_detects_head_swap_after_scan(self):
        BASE_SHA = 'b' * 40
        repo = {'full_name': 'Alexio00/HEALTH', 'id': 1408460030,
                'owner': {'id': OWNER}}
        event = {'repository': repo,
                 'pull_request': {'number': 9, 'head': {'sha': HEAD},
                                  'base': {'ref': 'pwa', 'sha': BASE_SHA,
                                           'repo': repo}}}
        initial = {'state': 'open', 'head': {'sha': HEAD},
                   'base': {'ref': 'pwa', 'sha': BASE_SHA, 'repo': repo},
                   'user': {'id': 22}, 'body': None, 'changed_files': 1}
        changed = {**initial, 'head': {'sha': 'c' * 40}}
        file_data = [{'status': 'modified', 'filename': 'frontend/app.js'}]
        tree = {'frontend/app.js': ('blob', '100644')}
        with patch('trusted_pr_scope.api', side_effect=[initial, file_data, changed]) as network:
            with patch('trusted_pr_scope.git_tree', return_value=tree):
                with self.assertRaisesRegex(ScopeStop, 'pr_changed_during_scan'):
                    check_event(event, 'synthetic-readonly-token')

    def test_git_change_modes_fail_closed(self):
        path = 'frontend/app.js'
        with self.assertRaises(ScopeStop):
            check_scope([{'status': 'added', 'filename': path}], 'pwa', 22, '',
                        HEAD, {path: ('blob','100644')}, {path: ('blob','100644')})
        with self.assertRaises(ScopeStop):
            check_scope([{'status': 'removed', 'filename': path}], 'pwa', 22, '',
                        HEAD, {path: ('blob','100644')}, {path: ('blob','100644')})

    def test_r2_config_env_variants_and_nul_path_denied(self):
        for mode, path in (("pwa", "frontend/config.env.production"),
                           ("pwa", "frontend/file\\0.js"),
                           ("pwa", "frontend/file%00.js"),
                           ("scheduler-code", "scripts/scheduler/config.env.production"),
                           ("writer-code", "scripts/writer/config.env.production")):
            with self.subTest(mode=mode, path=repr(path)), self.assertRaises(ScopeStop):
                verify(path, mode, OWNER, "WRITER-CONTROL: " + HEAD)

    def test_r2_boolean_size_rejected(self):
        doc = {"type": "file", "path": ".github/workflows/health-trusted-scope.yml",
               "sha": HEAD, "size": True}
        with patch("trusted_pr_scope.api", return_value=doc):
            with self.assertRaisesRegex(ScopeStop, "trusted_default_workflow_blob_changed"):
                check_trusted_policy_release(HEAD, HEAD, HEAD, HEAD, "synthetic")

    def test_r2_rename_must_not_leave_old_or_replace_existing(self):
        old, new = "frontend/old.js", "frontend/new.js"
        entry = {"filename": new, "previous_filename": old, "status": "renamed"}
        blob = ("blob", "100644")
        with self.assertRaisesRegex(ScopeStop, "renamed_tree_state_invalid"):
            check_scope([entry], "pwa", 22, "", HEAD,
                        {old: blob, new: blob}, {old: blob})
        with self.assertRaisesRegex(ScopeStop, "renamed_tree_state_invalid"):
            check_scope([entry], "pwa", 22, "", HEAD,
                        {new: blob}, {old: blob, new: blob})

    def test_r2_event_base_identity_fails_before_network(self):
        repo = {"full_name": "Alexio00/HEALTH", "id": 1408460030,
                "owner": {"id": OWNER}}
        event = {"repository": repo,
                 "pull_request": {"number": 9, "head": {"sha": HEAD},
                                  "base": {"ref": "pwa", "sha": "b" * 40,
                                           "repo": repo}}}
        with patch("trusted_pr_scope.api") as network:
            for bad in ({**repo, "id": 42},
                        {**repo, "owner": {"id": 42}},
                        {**repo, "full_name": "other/repo"}):
                with self.subTest(bad=bad), self.assertRaises(ScopeStop):
                    check_event({**event, "repository": bad}, "synthetic")
                with self.subTest(bad_base=bad), self.assertRaises(ScopeStop):
                    check_event({**event, "pull_request": {
                        **event["pull_request"],
                        "base": {**event["pull_request"]["base"], "repo": bad}}},
                        "synthetic")
            network.assert_not_called()

    def test_duplicate_and_unsafe_segments(self):
        items, ht, bt = scenario("frontend/app.js")
        with self.assertRaises(ScopeStop):
            check_scope(items + items, "pwa", 1, "", HEAD, ht, bt)
        for path in ("frontend/../db/x", "frontend//x", "frontend/.hidden/x", "frontend/secrets/a.json"):
            with self.assertRaises(ScopeStop):
                verify(path)


if __name__ == "__main__":
    unittest.main()
