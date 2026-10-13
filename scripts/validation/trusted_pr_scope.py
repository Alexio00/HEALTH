"""Trusted read-only PR scope policy. Never executes PR files or imports from PR.

This must run from an independently accepted exact main code SHA under a
base-controlled event. A candidate-owned pull_request job is NOT a trusted
issuer merely because it has the same name or the GitHub Actions App source.
"""
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

REPO = "Alexio00/HEALTH"
OWNER_ID = 308028794
SHA = re.compile(r"[0-9a-f]{40}\Z")
PWA_DOCS = {"AGENTS.md", "docs/PWA_RELEASE.md"}
PWA_CONTROLS = {
    ".github/workflows/deploy-pages.yml",
    ".github/workflows/code-validation.yml",
    ".github/workflows/pwa-scope.yml",
}
SCHEDULER_FILES = {
    "scripts/automation/supabase_keepalive.py",
    "scripts/automation/test_scheduler_transfer.py",
    "scripts/automation/health_activity.mjs",
    "scripts/automation/health_activity.test.mjs",
    "docs/SCHEDULER_CONSOLIDATION_RU.md",
    "docs/HEALTH_ACTIVITY_RU.md",
}
SCHEDULER_CONTROLS = {".github/workflows/health-scheduler-validation.yml"}
DENIED_SEGMENTS = {"private", "secrets", "records", "sources", "labs"}
DENIED_SUFFIXES = (".sql", ".pem", ".key", ".env")
VALID_STATUSES = {"added", "modified", "removed", "renamed", "changed", "copied"}


class ScopeStop(RuntimeError):
    pass


def sha40(value):
    return isinstance(value, str) and SHA.fullmatch(value) is not None


def safe_path(path, controls):
    if not isinstance(path, str) or not path or path.startswith("/") or "\\" in path:
        raise ScopeStop("invalid_path")
    parts = path.split("/")
    if any(not part or part in (".", "..") for part in parts):
        raise ScopeStop("noncanonical_path")
    if any(part.startswith(".") for part in parts) and path not in controls:
        raise ScopeStop("hidden_or_unsafe_path")
    if any(part.casefold() in DENIED_SEGMENTS for part in parts):
        raise ScopeStop("private_path_forbidden")
    if path.casefold().endswith(DENIED_SUFFIXES):
        raise ScopeStop("backend_or_secret_extension_forbidden")


def check_scope(changes, mode, author_id, body, head, tree_head, tree_base):
    """Full old+new path check (including renames and deletion) and tree modes."""
    if mode not in ("pwa", "scheduler-code") or not sha40(head):
        raise ScopeStop("unsupported_base_or_head")
    if not changes or len(changes) > 3000:
        raise ScopeStop("empty_or_oversized_pr")
    controls = PWA_CONTROLS if mode == "pwa" else SCHEDULER_CONTROLS
    touched_controls = []
    seen = set()
    for entry in changes:
        if entry.get("status") not in VALID_STATUSES:
            raise ScopeStop("unknown_change_status")
        new = entry.get("filename")
        old = entry.get("previous_filename") if entry["status"] == "renamed" else None
        if entry["status"] == "renamed" and not old:
            raise ScopeStop("rename_missing_previous_path")
        if new in seen:
            raise ScopeStop("duplicate_file_entry")
        seen.add(new)
        for path in (new, old):
            if path is None:
                continue
            safe_path(path, controls)
            if mode == "pwa":
                permitted = path.startswith("frontend/") or path in PWA_DOCS or path in controls
                control = path in controls or path.startswith("frontend/release/")
            else:
                permitted = (path.startswith("scripts/scheduler/")
                             or path in SCHEDULER_FILES or path in controls)
                control = path in controls
            if not permitted:
                raise ScopeStop("forbidden_" + mode.replace("-", "_") + "_path")
            if control:
                touched_controls.append(path)
        for path, tree in ((new, tree_head), (old or new, tree_base)):
            if path is None:
                continue
            item = tree.get(path)
            if item is not None and item != ("blob", "100644"):
                raise ScopeStop("nonregular_or_symlink_content")
        if entry["status"] != "removed" and new not in tree_head:
            raise ScopeStop("head_path_missing")
        if entry["status"] in ("removed", "renamed") and (old or new) not in tree_base:
            raise ScopeStop("base_path_missing")
    if touched_controls and not (author_id == OWNER_ID and
            isinstance(body, str) and
            ("PWA-RELEASE-CONTROL: " if mode == "pwa" else "SCHEDULER-CONTROL: ") + head
            in body.splitlines()):
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


def git_tree(token, commit):
    if not sha40(commit):
        raise ScopeStop("commit_sha_invalid")
    c = api("/repos/" + REPO + "/git/commits/" + commit, token)
    root = c.get("tree", {}).get("sha")
    if not sha40(root):
        raise ScopeStop("commit_tree_missing")
    data = api("/repos/" + REPO + "/git/trees/" + root + "?recursive=1", token)
    if data.get("truncated") is True or not isinstance(data.get("tree"), list):
        raise ScopeStop("tree_incomplete")
    return {e["path"]: (e.get("type"), e.get("mode")) for e in data["tree"]}


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
    head = event_pr.get("head", {}).get("sha")
    mode = event_pr.get("base", {}).get("ref")
    if (mode not in ("pwa", "scheduler-code") or not sha40(head)
            or current.get("state") != "open"
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
    return check_scope(changes, mode, current.get("user", {}).get("id"),
                       current.get("body") or "", head,
                       git_tree(token, head), git_tree(token, current["base"]["sha"]))


if __name__ == "__main__":
    try:
        if (os.getenv("GITHUB_ACTIONS") != "true"
                or os.getenv("GITHUB_REPOSITORY") != REPO
                or os.getenv("GITHUB_EVENT_NAME") != "pull_request_target"
                or os.getenv("GITHUB_WORKFLOW_REF") !=
                   REPO + "/.github/workflows/health-trusted-scope.yml@refs/heads/main"):
            raise ScopeStop("base_trusted_workflow_required")
        accepted = os.getenv("HEALTH_TRUSTED_POLICY_SHA")
        checked = os.popen("git rev-parse HEAD").read().strip()
        if not sha40(accepted) or accepted != checked:
            raise ScopeStop("accepted_trusted_policy_sha_required")
        with open(os.environ["GITHUB_EVENT_PATH"], encoding="utf-8") as file:
            print(json.dumps(check_event(json.load(file), os.getenv("GH_TOKEN")),
                             sort_keys=True))
    except ScopeStop as exc:
        print("FAIL: " + str(exc), file=sys.stderr)
        sys.exit(2)
