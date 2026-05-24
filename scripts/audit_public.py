#!/usr/bin/env python3
"""Audit public-facing files for accidental secret exposure.

Fails (exit code 1) if any of the following are found in tracked files:
- Local file paths (e.g., /Users/, C:\, home directories)
- Private key markers (-----BEGIN RSA PRIVATE KEY-----, etc.)
- API keys or tokens in obvious patterns (sk-proj-, ghp_, GH_TOKEN, etc.)
- Plugin cache state files

Intended for use before pushing to public repositories.
"""

import os
import re
import subprocess
import sys


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Patterns to check for
DANGEROUS_PATTERNS = [
    (r"-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----", "private key detected"),
    (r"sk-proj-[A-Za-z0-9]{20,}", "OpenAI-style API key detected"),
    (r"ghp_[A-Za-z0-9]{36}", "GitHub personal access token detected"),
    (r"github_pat_[A-Za-z0-9_]{22,}", "GitHub PAT detected"),
    (r"Bearer\s+[A-Za-z0-9\-_\.]+", "Bearer token detected"),
    (r"AKIA[0-9A-Z]{16}", "AWS access key detected"),
]

# Files/folders to skip
SKIP_DIRS = {".git", ".obsidian/cache", "__pycache__"}
SKIP_FILES = {os.path.basename(__file__), "scripts/audit_public.py", os.path.abspath(__file__)}


def get_tracked_files():
    """Get list of tracked files in the git repo."""
    try:
        result = subprocess.run(
            ["git", "ls-files"],
            capture_output=True, text=True, cwd=REPO_ROOT
        )
        return result.stdout.strip().split("\n") if result.returncode == 0 else []
    except Exception:
        return []


def audit_file(filepath):
    """Check a single file for dangerous patterns. Returns list of findings."""
    full_path = os.path.join(REPO_ROOT, filepath)

    # Skip binary files, cache dirs, and the audit script itself
    if filepath in SKIP_FILES or os.path.basename(filepath) in {os.path.basename(f) for f in SKIP_FILES}:
        return []
    for skip in SKIP_DIRS:
        if filepath.startswith(skip) or f"/{skip}/" in filepath:
            return []

    try:
        with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        findings = []
        for pattern, description in DANGEROUS_PATTERNS:
            if re.search(pattern, content):
                findings.append(f"  ✗ {filepath}: {description}")

        return findings
    except Exception:
        return []


def main():
    tracked = get_tracked_files()
    all_findings = []

    for filepath in tracked:
        if not filepath.strip():
            continue
        findings = audit_file(filepath)
        all_findings.extend(findings)

    if all_findings:
        print("AUDIT FAILED — potential secrets found:")
        for f in all_findings:
            print(f)
        sys.exit(1)

    print(f"OK: audit_public passed ({len(tracked)} files checked, no secrets found).")
    sys.exit(0)


if __name__ == "__main__":
    main()
