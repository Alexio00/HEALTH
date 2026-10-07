#!/usr/bin/env python3
"""Public repository secret-pattern guard.

Looks only for secret-like VALUES, not ordinary field names such as refresh_token.
This is defense-in-depth; GitHub secret scanning remains independent.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKIP_DIRS = {".git", "node_modules", "dist", "coverage"}
SKIP_SUFFIXES = {".md"}
SKIP_NAMES = {"public_secret_guard.py"}

PATTERNS = {
    "supabase_secret_key": re.compile(r"sb_secret_[A-Za-z0-9_-]{20,}"),
    "database_url_password": re.compile(r"postgres(?:ql)?://[^:\s]+:[^@/\s]{8,}@"),
    "client_secret_value": re.compile(r"""client_secret\s*[:=]\s*["']?[A-Za-z0-9_-]{20,}""", re.I),
    "refresh_token_value": re.compile(r"""refresh_token\s*[:=]\s*["']?(?:1//|[A-Za-z0-9_-]{40,})""", re.I),
}

findings: list[str] = []
for path in ROOT.rglob("*"):
    if not path.is_file():
        continue
    rel = path.relative_to(ROOT)
    if any(part in SKIP_DIRS for part in rel.parts):
        continue
    if path.suffix.lower() in SKIP_SUFFIXES or path.name in SKIP_NAMES:
        continue
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        continue
    for label, pattern in PATTERNS.items():
        if pattern.search(text):
            findings.append(f"{rel}: {label}")

if findings:
    print("FAIL public secret-pattern guard")
    for finding in findings:
        print(finding)
    raise SystemExit(1)

print("PASS public secret-pattern guard")
