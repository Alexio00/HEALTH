import unittest
from release_train_scope import (
    classify, SAFE, REVIEW, BLOCK,
)

class ReleaseTrainScopeTests(unittest.TestCase):
    def test_safe_frontend_candidate(self):
        self.assertEqual(classify(["frontend/app.js", "frontend/styles.css"], "pwa").verdict, SAFE)

    def test_ui_workflow_auth_and_release_require_review(self):
        for path in ("frontend/oauth-test/consent.mjs", "frontend/sw.js",
                     "frontend/supabase-client.js", "frontend/release/build.mjs",
                     ".github/workflows/deploy-pages.yml", "AGENTS.md", "docs/PWA_RELEASE.md"):
            with self.subTest(path=path):
                self.assertEqual(classify([path], "pwa").verdict, REVIEW)

    def test_backend_sql_and_writer_rejected_on_frontend(self):
        for path in ("scripts/writer/chat_worker.py", "db/core.sql",
                     "supabase/migrations/2026.sql", ".github/workflows/writer-authorization.yml",
                     "scripts/validation/public_secret_guard.py"):
            with self.subTest(path=path):
                self.assertEqual(classify([path], "pwa").verdict, BLOCK)

    def test_scheduler_code_only(self):
        self.assertEqual(classify(
            ["scripts/scheduler/complete_archive.py", "scripts/automation/supabase_keepalive.py"],
            "scheduler-code").verdict, SAFE)
        self.assertEqual(classify([".github/workflows/health-scheduler-validation.yml"],
                                  "scheduler-code").verdict, REVIEW)

    def test_scheduler_is_not_an_authorized_launcher(self):
        for path in (".github/workflows/health-complete-backup.yml",
                     ".github/workflows/writer-authorization.yml",
                     "scripts/writer/chat_worker.py", "frontend/app.js",
                     "supabase/migrations/new.sql"):
            with self.subTest(path=path):
                self.assertEqual(classify([path], "scheduler-code").verdict, BLOCK)

    def test_writer_still_requires_independent_review(self):
        self.assertEqual(classify(["scripts/writer/chat_worker.py"], "writer-code").verdict, REVIEW)
        self.assertEqual(classify(["supabase/migrations/20261014_x.sql"], "writer-code").verdict, REVIEW)
        self.assertEqual(classify(["frontend/app.js"], "writer-code").verdict, BLOCK)

    def test_bad_input_closed(self):
        for paths, target in (([], "pwa"), (["frontend/app.js"], "main"),
                              (["../frontend/app.js"], "pwa"),
                              (["frontend\\app.js"], "pwa"),
                              (["frontend/app.js", "frontend/app.js"], "pwa"),
                              (["frontend/./app.js"], "pwa"),
                              (["/frontend/app.js"], "pwa")):
            with self.subTest(paths=paths, target=target):
                self.assertEqual(classify(paths, target).verdict, BLOCK)

    def test_mixed_change_is_blocked_not_partially_accepted(self):
        self.assertEqual(classify(["frontend/app.js", "scripts/writer/publish.py"], "pwa").verdict, BLOCK)

if __name__ == "__main__":
    unittest.main()
