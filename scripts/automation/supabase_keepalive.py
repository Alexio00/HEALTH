"""Read-only Supabase keepalive for the consolidated, owner-approved HEALTH scheduler.

Never emits connection strings or medical data. Do not use on a pull request.
"""
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "writer"))
from session_pooler_tls import install_ca, runtime, SafeStop

REPOSITORY = "Alexio00/HEALTH"
ROLE = "health_backup_reader"
PROJECT = "ffvqgbslvjocbwfurxrv"


class KeepaliveStop(RuntimeError):
    pass


def validate_context(environ):
    if environ.get("GITHUB_ACTIONS") != "true":
        raise KeepaliveStop("actions_context_required")
    if environ.get("GITHUB_REPOSITORY") != REPOSITORY:
        raise KeepaliveStop("repository_mismatch")
    if environ.get("GITHUB_REF") != "refs/heads/main":
        raise KeepaliveStop("default_branch_required")
    if environ.get("GITHUB_EVENT_NAME") not in ("schedule", "workflow_dispatch"):
        raise KeepaliveStop("scheduled_or_owner_dispatch_required")
    if not re.fullmatch(r"[0-9a-f]{40}", environ.get("GITHUB_SHA", "")):
        raise KeepaliveStop("exact_sha_required")
    if environ.get("HEALTH_KEEPALIVE_ACCEPTED_SHA") != environ["GITHUB_SHA"]:
        raise KeepaliveStop("unaccepted_executor_sha")


def main():
    validate_context(os.environ)
    uri = os.environ.get("HEALTH_KEEPALIVE_DB_URL", "")
    if not uri or not os.environ.get("HEALTH_SUPABASE_CA_PEM"):
        raise KeepaliveStop("missing_private_configuration")

    # The accepted Session transport already pins CA, role, project and TLS.
    with tempfile.TemporaryDirectory(prefix="health-keepalive-") as work:
        ca = Path(work) / "ca.pem"
        install_ca(ca)
        sql = ("BEGIN READ ONLY; SET LOCAL statement_timeout='12s'; "
               "SELECT CASE WHEN current_user='health_backup_reader' "
               "AND session_user='health_backup_reader' "
               "AND current_setting('transaction_read_only')='on' "
               "THEN 1 ELSE 0 END; ROLLBACK;")
        with runtime(uri, PROJECT, ROLE, ca) as env:
            env["PGOPTIONS"] = "-c default_transaction_read_only=on"
            try:
                p = subprocess.run(
                    ["psql", "-X", "-qAt", "-v", "ON_ERROR_STOP=1", "-c", sql],
                    env=env, capture_output=True, text=True, timeout=35
                )
            except Exception:
                raise KeepaliveStop("keepalive_client_failure") from None
            if p.returncode != 0 or p.stdout.strip() != "1":
                raise KeepaliveStop("keepalive_readonly_verification_failed")
    print("PASS: HEALTH Supabase read-only keepalive; no clinical payload")


if __name__ == "__main__":
    try:
        main()
    except (KeepaliveStop, SafeStop) as exc:
        print("STOPPED: " + str(exc), file=sys.stderr)
        sys.exit(2)
    except Exception:
        print("STOPPED: unexpected_keepalive_failure", file=sys.stderr)
        sys.exit(2)
