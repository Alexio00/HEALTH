"""Trusted read-only PR scope policy. Never executes PR files or imports from PR.

This must run from an independently accepted exact main code SHA under a
base-controlled event. A candidate-owned pull_request job is NOT a trusted
issuer merely because it has the same name or the GitHub Actions App source.
"""
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

REPO = "Alexio00/HEALTH"
OWNER_ID = 308028794
SHA = re.compile(r"[0-9a-f]{40}\Z")
PWA_DOCS = {"AGENTS.md", "docs/PWA_RELEASE.md"}
PWA_CONTROLS = set() # No PR-controlled workflow or release checks
SCHEDULER_FILES = {
    "scripts/automation/supabase_keepalive.py",
    "scripts/automation/test_scheduler_transfer.py",
    "scripts/automation/health_activity.mjs",
    "scripts/automation/health_activity.test.mjs",
    "docs/SCHEDULER_CONSOLIDATION_RU.md",
    "docs/HEALTH_ACTIVITY_RU.md",
}
SCHEDULER_CONTROLS = set()
WRITER_CONTROLS = set()
WRITER_PREFIXES = ("scripts/writer/", "scripts/validation/", "db/", "supabase/",
                   "docs/proposals/")
WRITER_SQL_PREFIXES = ("scripts/writer/", "scripts/validation/", "db/", "supabase/")
WRITER_OWNER_ATTESTATION = "WRITER-CONTROL: "
DENIED_SEGMENTS = {"private", "secrets", "records", "sources", "labs", "auth", "oauth", "credentials", "tokens", "keys", "release", "deploy", "service-worker", "service_role" }
SENSITIVE_NAMES = ("secret", "credential", "token", "password", "auth", "oauth", "supabase", "writer", "workflow", "release", "deploy", "service-worker", "serviceworker", "apikey", "api-key")
DENIED_SUFFIXES = (".sql", ".pem", ".key", ".env", ".p12", ".pfx", ".jks", ".asc", ".gpg")
VALID_STATUSES = {"added", "modified", "removed", "renamed", "changed"}


class ScopeStop(RuntimeError):
    pass


def sha40(value):
    return isinstance(value, str) and SHA.fullmatch(value) is not None


def safe_path(path, controls, writer_sql=False):
    if (not isinstance(path, str) or not path or path.startswith("/")
            or "\\" in path or any(ord(char) < 32 or ord(char) == 127 for char in path)
            or "%00" in path.casefold()):
        raise ScopeStop("invalid_path")
    parts = path.split("/")
    if any(not part or part in (".", "..") for part in parts):
        raise ScopeStop("noncanonical_path")
    if any(part.startswith(".") for part in parts) and path not in controls:
        raise ScopeStop("hidden_or_unsafe_path")
    if any(part.casefold() in DENIED_SEGMENTS for part in parts):
        raise ScopeStop("private_path_forbidden")
    if parts[0] == "frontend" and not writer_sql and any(
            term in part.casefold() for part in parts[1:] for term in SENSITIVE_NAMES):
        raise ScopeStop("sensitive_frontend_file_forbidden")
    # Reject dotted .env variants, not just the last filename suffix.
    filename = parts[-1].casefold()
    if "env" in filename.split(".") or filename.endswith(DENIED_SUFFIXES):
        if not (writer_sql and path.endswith(".sql") and path.startswith(WRITER_SQL_PREFIXES)):
            raise ScopeStop("backend_or_secret_extension_forbidden")


def check_scope(changes, mode, author_id, body, head, tree_head, tree_base):
    """Full old+new path check (including renames and deletion) and tree modes."""
    if mode not in ("pwa", "scheduler-code", "writer-code") or not sha40(head):
        raise ScopeStop("unsupported_base_or_head")
    if not changes or len(changes) > 3000:
        raise ScopeStop("empty_or_oversized_pr")
    controls = {"pwa": PWA_CONTROLS, "scheduler-code": SCHEDULER_CONTROLS,
                "writer-code": WRITER_CONTROLS}[mode]
    touched_controls = []
    seen = set()
    for entry in changes:
        if entry.get("status") not in VALID_STATUSES:
            raise ScopeStop("unknown_change_status")
        new = entry.get("filename")
        old = entry.get("previous_filename") if entry["status"] == "renamed" else None
        if entry["status"] == "renamed" and not old:
            raise ScopeStop("rename_missing_previous_path")
        if new in seen or (old is not None and old in seen):
            raise ScopeStop("duplicate_file_entry")
        seen.add(new)
        if old is not None:
            seen.add(old)
        for path in (new, old):
            if path is None:
                continue
            safe_path(path, controls, writer_sql=(mode == "writer-code"))
            if mode == "pwa":
                permitted = path.startswith("frontend/") or path in PWA_DOCS
                control = path in controls
            elif mode == "scheduler-code":
                permitted = (path.startswith("scripts/scheduler/")
                             or path in SCHEDULER_FILES)
                control = path in controls
            else:
                permitted = (path.startswith(WRITER_PREFIXES)
                             or path.startswith("docs/WRITER_")
                             )
                # All Writer changes are privileged candidates: owner acknowledgement
                # here is *not* clinical acceptance or an independent review.
                control = permitted
            if mode == "writer-code" and path in (
                    "scripts/validation/trusted_pr_scope.py",
                    "scripts/validation/test_trusted_pr_scope.py",
                    "scripts/validation/public_secret_guard.py"):
                raise ScopeStop("trusted_policy_file_forbidden_in_writer_train")
            if not permitted:
                raise ScopeStop("forbidden_" + mode.replace("-", "_") + "_path")
            if control:
                touched_controls.append(path)
        status = entry["status"]
        head_item = tree_head.get(new)
        base_item = tree_base.get(old or new)
        if status == "added":
            if head_item != ("blob", "100644") or base_item is not None:
                raise ScopeStop("added_tree_state_invalid")
        elif status == "removed":
            if head_item is not None or base_item != ("blob", "100644"):
                raise ScopeStop("removed_tree_state_invalid")
        elif status == "renamed":
            if old == new or head_item != ("blob", "100644") or base_item != ("blob", "100644"):
                raise ScopeStop("renamed_tree_state_invalid")
        elif head_item != ("blob", "100644") or base_item != ("blob", "100644"):
            raise ScopeStop("changed_tree_state_invalid")
    prefix = {"pwa": "PWA-RELEASE-CONTROL: ",
              "scheduler-code": "SCHEDULER-CONTROL: ",
              "writer-code": WRITER_OWNER_ATTESTATION}[mode]
    if touched_controls and not (author_id == OWNER_ID and
            isinstance(body, str) and
            prefix + head in body.splitlines()):
        raise ScopeStop("control_changes_require_owner_exact_head")
    return {"scope": mode, "checked_files": len(changes),
            "control_paths": len(set(touched_controls))}


def api(path, token):
    if not token:
        raise ScopeStop("read_only_token_required")
    url = "https://api.github.com" + path
    request = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "Authorization": "Bearer " + token,
        "User-Agent": "HEALTH-immutable-readonly-scope",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.load(response)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
        raise ScopeStop("github_api_read_failed") from None


TRUSTED_WORKFLOW_PATH = ".github/workflows/health-trusted-scope.yml"


def check_trusted_policy_release(accepted, checked, event_sha, expected_blob, token):
    """Fail closed on accepted policy commit AND immutable default-workflow blob.

    The two pins are independent: main HEAD may advance without silently
    accepting a new executable policy or changed issuing workflow. The event
    SHA is GitHub's default-main workflow source for pull_request_target.
    This does not itself prove Ruleset issuer identity or authorize merging.
    """
    if (not sha40(accepted) or not sha40(checked) or not sha40(event_sha)
            or not sha40(expected_blob) or checked != accepted):
        raise ScopeStop("independent_policy_pin_required")
    metadata = api("/repos/" + REPO + "/contents/" + TRUSTED_WORKFLOW_PATH +
                   "?ref=" + event_sha, token)
    if (not isinstance(metadata, dict)
            or metadata.get("type") != "file"
            or metadata.get("path") != TRUSTED_WORKFLOW_PATH
            or metadata.get("sha") != expected_blob
            or not isinstance(metadata.get("size"), int)
            or metadata["size"] <= 0):
        raise ScopeStop("trusted_default_workflow_blob_changed")
    return True


def git_tree(token, commit):
    if not sha40(commit):
        raise ScopeStop('commit_sha_invalid')
    c = api('/repos/' + REPO + '/git/commits/' + commit, token)
    if not isinstance(c, dict) or not isinstance(c.get('tree'), dict):
        raise ScopeStop('commit_metadata_invalid')
    root = c['tree'].get('sha')
    if not sha40(root):
        raise ScopeStop('commit_tree_missing')
    data = api('/repos/' + REPO + '/git/trees/' + root + '?recursive=1', token)
    if (not isinstance(data, dict) or data.get('truncated') is not False
            or not isinstance(data.get('tree'), list)):
        raise ScopeStop('tree_incomplete')
    allowed = {('tree','040000'), ('blob','100644'), ('blob','100755'),
               ('blob','120000'), ('commit','160000')}
    result = {}
    for entry in data['tree']:
        if not isinstance(entry, dict):
            raise ScopeStop('tree_entry_invalid')
        path, mode, kind = entry.get('path'), entry.get('mode'), entry.get('type')
        if (not isinstance(path, str) or not path or path.startswith('/')
                or chr(92) in path or any(part in ('', '.', '..') for part in path.split('/'))
                or (kind, mode) not in allowed or path in result
                or not sha40(entry.get('sha'))):
            raise ScopeStop('tree_entry_invalid_or_duplicate')
        result[path] = (kind, mode)
    return result

def check_event(event, token):
    """Read the current PR from GitHub; reject stale dispatch/event or changed HEAD."""
    event_pr = event.get("pull_request")
    repo = event.get("repository", {})
    if (repo.get("full_name") != REPO or not isinstance(event_pr, dict)
            or not isinstance(event_pr.get("number"), int)
            or event_pr["number"] < 1):
        raise ScopeStop("event_identity_invalid")
    number = event_pr["number"]
    current = api("/repos/" + REPO + "/pulls/" + str(number), token)
    if not isinstance(current, dict) or not isinstance(current.get("head"), dict) or not isinstance(current.get("base"), dict) or not isinstance(current.get("user"), dict):
        raise ScopeStop("current_pr_metadata_invalid")
    head = event_pr.get("head", {}).get("sha")
    mode = event_pr.get("base", {}).get("ref")
    if (mode not in ("pwa", "scheduler-code", "writer-code") or not sha40(head)
            or current.get("state") != "open"
            or type(current.get("changed_files")) is not int
            or not 0 < current["changed_files"] <= 3000
            or type(current["user"].get("id")) is not int
            or current.get("head", {}).get("sha") != head
            or current.get("base", {}).get("ref") != mode
            or current.get("base", {}).get("sha") != event_pr.get("base", {}).get("sha")
            or not sha40(current.get("base", {}).get("sha"))):
        raise ScopeStop("stale_head_or_wrong_base")
    changes = []
    for page in range(1, 32):
        result = api("/repos/" + REPO + "/pulls/" + str(number) +
                     "/files?per_page=100&page=" + str(page), token)
        if not isinstance(result, list):
            raise ScopeStop("pr_files_invalid")
        changes.extend(result)
        if len(result) < 100:
            break
    else:
        raise ScopeStop("pr_file_page_limit")
    if len(changes) != current.get("changed_files"):
        raise ScopeStop("incomplete_pr_file_list")
    body = current.get("body") or ""
    if not isinstance(body, str):
        raise ScopeStop("pr_body_invalid")
    result = check_scope(changes, mode, current["user"]["id"],
                         body, head, git_tree(token, head),
                         git_tree(token, current["base"]["sha"]))
    final = api("/repos/" + REPO + "/pulls/" + str(number), token)
    if (not isinstance(final, dict)
            or not isinstance(final.get("head"), dict)
            or not isinstance(final.get("base"), dict)
            or not isinstance(final.get("user"), dict)
            or final.get("state") != "open"
            or final["head"].get("sha") != head
            or final["base"].get("sha") != current["base"]["sha"]
            or final["base"].get("ref") != mode
            or final["user"].get("id") != current["user"]["id"]
            or final.get("body") != current.get("body")
            or final.get("changed_files") != len(changes)):
        raise ScopeStop("pr_changed_during_scan")
    return result


if __name__ == "__main__":
    try:
        if (os.getenv("GITHUB_ACTIONS") != "true"
                or os.getenv("GITHUB_REPOSITORY") != REPO
                or os.getenv("GITHUB_EVENT_NAME") != "pull_request_target"
                or os.getenv("GITHUB_WORKFLOW_REF") !=
                   REPO + "/.github/workflows/health-trusted-scope.yml@refs/heads/main"):
            raise ScopeStop("base_trusted_workflow_required")
        accepted = os.getenv("HEALTH_TRUSTED_POLICY_SHA")
        checked = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, timeout=10).strip()
        check_trusted_policy_release(
            accepted, checked, os.getenv("GITHUB_SHA"),
            os.getenv("HEALTH_TRUSTED_WORKFLOW_BLOB_SHA"),
            os.getenv("GH_TOKEN"))
        with open(os.environ["GITHUB_EVENT_PATH"], encoding="utf-8") as file:
            print(json.dumps(check_event(json.load(file), os.getenv("GH_TOKEN")),
                             sort_keys=True))
    except ScopeStop as exc:
        print("FAIL: " + str(exc), file=sys.stderr)
        sys.exit(2)
