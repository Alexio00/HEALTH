#!/usr/bin/env python3
"""Fail-closed credential pattern guard for public Git-tracked text objects.

Not a history, binary archive, or private-locator clearance tool.
"""
from __future__ import annotations
import argparse
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote

BINARY_SUFFIXES = frozenset({'.png', '.jpg', '.jpeg', '.gif', '.webp', '.pdf', '.zip', '.woff', '.woff2', '.ico', '.gz', '.tar'})
PATTERNS = {
    'supabase_secret_key': re.compile(r'\bsb_secret_[A-Za-z0-9_-]{20,}\b'),
    'database_url_password': re.compile(r'\bpostgres(?:ql)?://[^:\s]+:[^@/\s]{8,}@', re.I),
    'client_secret_value': re.compile(r'''\bclient_secret\s*["']?\s*[:=]\s*["']?\s*[A-Za-z0-9_-]{20,}''', re.I),
    'refresh_token_value': re.compile(r'''\brefresh_token\s*["']?\s*[:=]\s*["']?\s*(?:1//|[A-Za-z0-9_-]{40,})''', re.I),
}

def _entries(root: Path):
    """Yield (relative path, blob bytes); never trust a mutable worktree copy."""
    git = subprocess.run(['git', '-C', str(root), 'rev-parse', '--show-toplevel'], capture_output=True, text=True)
    if git.returncode == 0 and Path(git.stdout.strip()).resolve() == root:
        result = subprocess.run(['git', '-C', str(root), 'ls-files', '--stage', '-z'], capture_output=True)
        if result.returncode != 0:
            raise RuntimeError('cannot enumerate Git index')
        for entry in result.stdout.split(b'\0'):
            if not entry:
                continue
            try:
                meta, rawpath = entry.split(b'\t', 1)
                mode, oid, stage = meta.split()
            except ValueError as exc:
                raise RuntimeError('invalid Git index entry') from exc
            if stage != b'0':
                raise RuntimeError('unmerged Git index entry')
            if mode not in (b'100644', b'100755', b'120000'):
                raise RuntimeError('unsupported Git index file type')
            rel = Path(os.fsdecode(rawpath))
            # Symlink destinations are literal Git blobs, irrespective of suffix.
            if mode != b'120000' and rel.suffix.lower() in BINARY_SUFFIXES:
                continue
            blob = subprocess.run(['git', '-C', str(root), 'cat-file', 'blob', oid.decode('ascii')], capture_output=True)
            if blob.returncode != 0:
                raise RuntimeError('cannot read Git index blob')
            yield rel, blob.stdout
    else:
        failures = []
        def onerror(exc):
            failures.append(exc)
        for base, dirs, files in os.walk(root, followlinks=False, onerror=onerror):
            # .git contents are metadata, not public payloads.
            dirs[:] = [d for d in dirs if d != '.git']
            # Directory symlinks hold public path payloads in standalone mode too.
            links = [d for d in dirs if (Path(base) / d).is_symlink()]
            dirs[:] = [d for d in dirs if d not in links]
            for name in sorted(files + links):
                path = Path(base) / name
                rel = path.relative_to(root)
                if path.is_symlink():
                    yield rel, os.fsencode(os.readlink(path))
                elif rel.suffix.lower() not in BINARY_SUFFIXES:
                    yield rel, path.read_bytes()
        if failures:
            raise OSError('cannot enumerate one or more directories')

def _matches(content: str):
    versions = [content]
    # Bounded percent decoding; never an unbounded transformation loop.
    for _ in range(2):
        next_content = unquote(versions[-1])
        if next_content == versions[-1]:
            break
        versions.append(next_content)
    for label, pattern in PATTERNS.items():
        if any(pattern.search(v) for v in versions):
            yield label

def check(root: Path):
    findings, errors = [], []
    try:
        root = root.resolve(strict=True)
        if not root.is_dir():
            raise NotADirectoryError('not a directory')
        for rel, blob in _entries(root):
            try:
                content = blob.decode('utf-8', errors='strict')
            except UnicodeError as exc:
                errors.append((rel.as_posix(), 'unreadable: ' + type(exc).__name__))
                continue
            for kind in _matches(content):
                findings.append((rel.as_posix(), kind))
    except (OSError, RuntimeError, ValueError) as exc:
        errors.append(('.', 'cannot complete scan: ' + type(exc).__name__))
    return findings, errors

def scan(root: Path):
    """Compatibility API. Errors are returned as scan_error findings (never PASS)."""
    findings, errors = check(root)
    return findings + [(path, 'scan_error') for path, _ in errors]

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    findings, errors = check(args.root)
    if findings or errors:
        print('FAIL public secret-pattern guard')
        for path, kind in findings:
            print(f'{path!r}: {kind}')
        for path, why in errors:
            print(f'{path!r}: scan_error ({why})')
        return 1
    print('PASS public secret-pattern guard')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
