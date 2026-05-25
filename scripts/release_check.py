#!/usr/bin/env python3
"""Release checks for the public repository."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKIP_FILES = {
    "github-skill-hunt.md",
}
SKIP_DIRS = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}

CHECKS = [
    ("private_path", re.compile(r"/Users/|/home/[^/\s]+")),
    ("private_key", re.compile(r"BEGIN [A-Z ]*PRIVATE KEY")),
    ("openai_style_key", re.compile(r"\bsk-[A-Za-z0-9_-]{12,}")),
    ("conflict_marker", re.compile(r"^(<<<<<<<|=======|>>>>>>>)$")),
]

REQUIRED_FILES = [
    "README.md",
    "LICENSE",
    ".gitignore",
    "docs/INTAKE.md",
    "docs/PUBLISHING.md",
    "docs/ROUTING.md",
    "docs/SECURITY.md",
    "scripts/install.sh",
    "scripts/release_check.py",
    "skills/_skill-router/SKILL.md",
    "skills/_skill-router/agents/openai.yaml",
    "skills/skill-intake/SKILL.md",
    "skills/skill-intake/agents/openai.yaml",
    "skills/skill-intake/scripts/intake_github_skill.py",
]

ALLOWLIST = {
    ("skills/skill-intake/scripts/intake_github_skill.py", "private_path"),
    ("scripts/release_check.py", "private_path"),
    ("scripts/release_check.py", "private_key"),
    ("scripts/release_check.py", "openai_style_key"),
    ("scripts/release_check.py", "conflict_marker"),
}


def main() -> int:
    findings = []
    for rel in REQUIRED_FILES:
        if not (ROOT / rel).is_file():
            findings.append(("missing_required_file", rel, 0, "required release file is missing"))

    for path in iter_files(ROOT):
        rel = path.relative_to(ROOT).as_posix()
        text = path.read_text(encoding="utf-8", errors="replace")
        for line_number, line in enumerate(text.splitlines(), start=1):
            for name, pattern in CHECKS:
                if (rel, name) in ALLOWLIST:
                    continue
                if pattern.search(line):
                    findings.append((name, rel, line_number, line.strip()[:180]))

    if findings:
        for name, rel, line_number, line in findings:
            print(f"{name}: {rel}:{line_number}: {line}")
        return 1

    print("release_check: ok")
    return 0


def iter_files(root: Path):
    for path in root.rglob("*"):
        if path.is_dir():
            continue
        if any(part in SKIP_DIRS for part in path.relative_to(root).parts):
            continue
        if path.name in SKIP_FILES:
            continue
        yield path


if __name__ == "__main__":
    raise SystemExit(main())
