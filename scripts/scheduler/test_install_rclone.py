"""Offline integration tests: an untrusted download cannot choose its own digest."""
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import zipfile

SCRIPT = Path(__file__).with_name("install_rclone.sh")


class RcloneInstallPinTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        fakebin = self.root / "fakebin"
        fakebin.mkdir()
        curl = fakebin / "curl"
        curl.write_text(
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            "test \"$#\" -eq 3\n"
            "test \"$1\" = -fsSLo\n"
            "cp \"$HEALTH_TEST_ARCHIVE\" \"$2\"\n",
            encoding="utf-8",
        )
        curl.chmod(0o755)
        self.archive = self.root / "synthetic.zip"
        with zipfile.ZipFile(self.archive, "w") as z:
            z.writestr(
                "rclone-v1.75.1-linux-amd64/rclone",
                "#!/usr/bin/env bash\necho synthetic-rclone-v1.75.1\n",
            )
        self.pin = hashlib.sha256(self.archive.read_bytes()).hexdigest()
        self.pathfile = self.root / "github-path"
        self.pathfile.write_text("", encoding="utf-8")
        self.env = {
            **os.environ,
            "PATH": str(fakebin) + os.pathsep + os.environ["PATH"],
            "RUNNER_TEMP": str(self.root),
            "GITHUB_PATH": str(self.pathfile),
            "HEALTH_TEST_ARCHIVE": str(self.archive),
            "HEALTH_RCLONE_VERSION": "1.75.1",
            "HEALTH_RCLONE_ARCHIVE_SHA256": self.pin,
        }

    def invoke(self, **changes):
        return subprocess.run(
            ["bash", str(SCRIPT)],
            env={**self.env, **changes},
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=15,
        )

    def test_matching_immutable_archive_pin_installs(self):
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("synthetic-rclone-v1.75.1", result.stdout)
        self.assertTrue((self.root / "bin/rclone").is_file())
        self.assertEqual(self.pathfile.read_text().strip(), str(self.root / "bin"))

    def test_wrong_independent_digest_cannot_install(self):
        result = self.invoke(HEALTH_RCLONE_ARCHIVE_SHA256="0" * 64)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root / "bin/rclone").exists())
        self.assertEqual(self.pathfile.read_text(), "")

    def test_missing_or_malformed_pin_fails_closed(self):
        for pin in ("", "not-a-digest", "a" * 63):
            with self.subTest(pin=pin):
                result = self.invoke(HEALTH_RCLONE_ARCHIVE_SHA256=pin)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse((self.root / "bin/rclone").exists())

    def test_untrusted_version_path_rejected(self):
        result = self.invoke(HEALTH_RCLONE_VERSION="../../unreviewed")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root / "bin/rclone").exists())


if __name__ == "__main__":
    unittest.main()
