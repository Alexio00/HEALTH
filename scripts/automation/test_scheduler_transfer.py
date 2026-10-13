"""Nonsecret synthetic checks for isolated HEALTH/scheduler-code candidate."""
import ast
import os
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCHEDULER = ROOT / "scripts" / "scheduler"
WORKFLOWS = ROOT / ".github" / "workflows"


class TransferSafety(unittest.TestCase):
    def test_all_backup_modules_parse_and_import_locally(self):
        main = (SCHEDULER / "complete_pipeline.py").read_text(encoding="utf-8")
        matches = re.search(r"EXECUTORS=\\[([^]]+)\\]", main)
        self.assertIsNotNone(matches)
        names = re.findall(r"'([^']+)'", matches.group(1))
        self.assertGreaterEqual(len(names), 15)
        for name in names:
            with self.subTest(name=name):
                path = SCHEDULER / name
                self.assertTrue(path.is_file())
                ast.parse(path.read_text(encoding="utf-8"))

    def test_no_private_original_identifiers_in_public_source(self):
        for path in SCHEDULER.iterdir():
            if path.suffix not in (".py", ".sh"):
                continue
            source = path.read_text(encoding="utf-8")
            with self.subTest(path=path.name):
                self.assertNotIn("Alexio000/SHEDULLER", source)
                self.assertNotRegex(source, r"(?i)[a-z0-9_.+-]+@(?:gmail|mail)\\.(?:com|ru)")
                self.assertNotRegex(source, r"""['"]1(?=[A-Za-z0-9_-]{29,}['"])(?=[A-Za-z0-9_-]*[A-Z])[A-Za-z0-9_-]{29,}['"]""")
                if path.name == "complete_pipeline.py":
                    self.assertNotIn("print(json.dumps(result))", source)

    def test_no_duplicate_production_workflows_in_scheduler_code(self):
        # Only main can contain live workflows, and its review is separate (PR #72).
        for name in (
            "health-supabase-keepalive.yml",
            "health-complete-backup.yml",
            "health-backup-preflight.yml",
            "health-backup-activate.yml",
            "health-activity.yml",
        ):
            with self.subTest(name=name):
                self.assertFalse((WORKFLOWS / name).exists())

    def test_accepted_executor_sha_independent_from_writer_main(self):
        runner = (SCHEDULER / "complete_pipeline.py").read_text(encoding="utf-8")
        self.assertIn("os.environ.get('HEALTH_BACKUP_PRODUCER_SHA','')", runner)
        self.assertIn("candidate_producer_sha_or_archive_binding_mismatch", runner)
        self.assertNotIn("os.environ['GITHUB_SHA'],serialized=True", runner)
        keepalive = (ROOT / "scripts" / "automation" / "supabase_keepalive.py").read_text(encoding="utf-8")
        self.assertIn("HEALTH_KEEPALIVE_ACCEPTED_SHA", keepalive)

    def test_keepalive_context_must_bind_repo_ref_sha(self):
        from importlib.util import module_from_spec, spec_from_file_location
        from unittest.mock import patch

        module_path = ROOT / "scripts" / "automation" / "supabase_keepalive.py"
        spec = spec_from_file_location("tested_health_keepalive", module_path)
        module = module_from_spec(spec)
        spec.loader.exec_module(module)
        sha = "a" * 40
        good = dict(
            GITHUB_ACTIONS="true", GITHUB_REPOSITORY="Alexio00/HEALTH",
            GITHUB_REF="refs/heads/main", GITHUB_EVENT_NAME="schedule",
            GITHUB_SHA=sha, HEALTH_KEEPALIVE_ACCEPTED_SHA=sha,
        )
        with patch.object(module.subprocess, "check_output", return_value=sha + "\\n"):
            module.validate_context(good)
            # Writer main can advance while accepted scheduler executor stays pinned.
            module.validate_context({**good, "GITHUB_SHA": "c" * 40})
            for key, value in (
                ("GITHUB_ACTIONS", "false"),
                ("GITHUB_REPOSITORY", "other/repo"),
                ("GITHUB_REF", "refs/heads/pwa"),
                ("GITHUB_EVENT_NAME", "pull_request"),
                ("HEALTH_KEEPALIVE_ACCEPTED_SHA", "b" * 40),
            ):
                with self.subTest(key=key), self.assertRaises(module.KeepaliveStop):
                    module.validate_context({**good, key: value})


if __name__ == "__main__":
    unittest.main()
