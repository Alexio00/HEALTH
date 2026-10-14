"""Non-authoritative source-scope classifier for HEALTH release-train proposals.

Important: this function handles *untrusted filenames* only. It does not examine
file contents, Git object types, grants, deployed workflows, RLS or signed
authorizations. Even a PASS is never an independent security review or release GO.
"""
from __future__ import annotations
import re
from dataclasses import dataclass

SAFE = "SCOPE_CANDIDATE_ONLY"
REVIEW = "INDEPENDENT_REVIEW_REQUIRED"
BLOCK = "WRONG_RELEASE_TRAIN"
VALID_TARGETS = {"pwa", "scheduler-code", "writer-code"}
SPECIAL_PWA = {
    "AGENTS.md", "docs/PWA_RELEASE.md",
    ".github/workflows/deploy-pages.yml",
    ".github/workflows/code-validation.yml",
}
SPECIAL_SCHEDULER = {".github/workflows/health-scheduler-validation.yml"}
SCHEDULER_DOCS = {"docs/SCHEDULER_CONSOLIDATION_RU.md", "docs/HEALTH_ACTIVITY_RU.md"}
SCHEDULER_TOOLS = {"scripts/automation/supabase_keepalive.py",
                   "scripts/automation/test_scheduler_transfer.py",
                   "scripts/automation/health_activity.mjs",
                   "scripts/automation/health_activity.test.mjs"}
WRITER_REVIEW = {"scripts/writer/", "scripts/validation/", "db/", "supabase/"}
INVALID = re.compile(r"(^/|^\\|\\|//|(?:^|/)\.\.?(/|$)|\x00)")


@dataclass(frozen=True)
class Decision:
    verdict: str
    reasons: tuple[str, ...]


def _valid_path(path: object) -> bool:
    return (isinstance(path, str) and bool(path) and not INVALID.search(path)
            and all(ord(ch) >= 32 for ch in path))


def classify(paths: list[str] | tuple[str, ...], target: str) -> Decision:
    if target not in VALID_TARGETS or not isinstance(paths, (list, tuple)) or not paths:
        return Decision(BLOCK, ("UNKNOWN_TARGET_OR_EMPTY_DIFF",))
    if len(paths) != len(set(map(str, paths))) or any(not _valid_path(p) for p in paths):
        return Decision(BLOCK, ("INVALID_OR_DUPLICATE_FILENAME",))
    review = set()
    forbidden = set()
    for path in paths:
        if target == "pwa":
            if path in SPECIAL_PWA:
                review.add(path)
            elif path.startswith("frontend/"):
                if (path.startswith("frontend/oauth-test/") or
                    path.startswith("frontend/release/") or
                    path in {"frontend/sw.js", "frontend/supabase-client.js"}):
                    review.add(path)
            else:
                forbidden.add(path)
        elif target == "scheduler-code":
            if path in SPECIAL_SCHEDULER:
                review.add(path)
            elif path.startswith("scripts/scheduler/") or path in SCHEDULER_TOOLS or path in SCHEDULER_DOCS:
                pass
            else:
                forbidden.add(path)
        elif target == "writer-code":
            if any(path.startswith(prefix) for prefix in WRITER_REVIEW):
                review.add(path)  # Security impact always possible.
            else:
                forbidden.add(path)
    if forbidden:
        return Decision(BLOCK, tuple(sorted(forbidden)))
    if review:
        return Decision(REVIEW, tuple(sorted(review)))
    return Decision(SAFE, ("PATH_SCOPE_ONLY_NOT_SECURITY_APPROVAL",))
