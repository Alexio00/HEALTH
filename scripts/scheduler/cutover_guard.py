"""Fail-closed one-time release context for changing the backup executor.

This is a defence-in-depth assertion, not evidence that another repository's
schedules or in-flight jobs were actually stopped. Independent owner readback
is mandatory before enabling the release variable.
"""
import re
import subprocess

OWNER = "308028794"
REPO = "Alexio00/HEALTH"
WORKFLOW = REPO + "/.github/workflows/health-backup-release.yml@refs/heads/main"
ACK = "LEGACY_SHEDULLER_PAUSED_AND_IDLE"


class CutoverStop(RuntimeError):
    pass


def sha(value):
    return isinstance(value, str) and re.fullmatch(r"[a-f0-9]{40}", value) is not None


def require_release_context(env, mode, checked_out_sha=None):
    if mode not in ("candidate", "activate"):
        raise CutoverStop("manual_release_mode_required")
    if (env.get("GITHUB_ACTIONS") != "true"
            or env.get("GITHUB_REPOSITORY") != REPO
            or env.get("GITHUB_REF") != "refs/heads/main"
            or env.get("GITHUB_EVENT_NAME") != "workflow_dispatch"
            or env.get("GITHUB_ACTOR_ID") != OWNER
            or env.get("GITHUB_WORKFLOW_REF") != WORKFLOW
            or env.get("HEALTH_COMPLETE_SERIALIZED") != "1"):
        raise CutoverStop("trusted_manual_release_workflow_required")
    # The variables alone cannot verify inter-repository state. The owner must
    # separately inspect disabled legacy schedules and absence of live runs.
    if (env.get("HEALTH_INREPO_RELEASE_ENABLED") != "true"
            or env.get("HEALTH_LEGACY_BACKUP_PAUSED") != "true"
            or env.get("HEALTH_INREPO_BACKUP_ENABLED") == "true"
            or env.get("HEALTH_RELEASE_ACK") != ACK
            or env.get("HEALTH_RELEASE_MODE") != mode):
        raise CutoverStop("explicit_legacy_pause_and_release_required")
    main_sha = env.get("HEALTH_RELEASE_MAIN_ACCEPTED_SHA")
    if not sha(main_sha) or main_sha != env.get("GITHUB_SHA"):
        raise CutoverStop("accepted_writer_main_sha_required")
    pin = env.get("HEALTH_BACKUP_EXECUTOR_SHA")
    if (not sha(pin)
            or pin != env.get("HEALTH_BACKUP_PRODUCER_SHA")
            or pin != env.get("HEALTH_RELEASE_EXPECTED_SHA")):
        raise CutoverStop("exact_scheduler_release_pin_required")
    if checked_out_sha is None:
        try:
            checked_out_sha = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], text=True
            ).strip()
        except Exception:
            raise CutoverStop("executor_checkout_unverifiable") from None
    if checked_out_sha != pin:
        raise CutoverStop("executor_checkout_not_accepted")
    return True
