#!/usr/bin/env python3
"""Check intake fixture decisions."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCANNER = ROOT / "skills" / "skill-intake" / "scripts" / "intake_github_skill.py"

EXPECTED = {
    "safe-new": "install-candidate",
    "explicit-platform": "explicit-only",
    "duplicate": "defer-duplicate",
    "manual-review": "manual-review",
    "reject": "reject",
}


def main() -> int:
    with tempfile.TemporaryDirectory() as temp:
        inventory = Path(temp) / "installed.json"
        inventory.write_text(
            json.dumps(
                {
                    "skills": [
                        {
                            "name": "skill-intake",
                            "description": "Evaluate GitHub-hosted or local Codex skills before installation.",
                            "path": "installed/skill-intake",
                        },
                        {
                            "name": "figma-use",
                            "description": "Use Figma operations when the user explicitly asks for Figma.",
                            "path": "installed/figma-use",
                        },
                    ]
                }
            ),
            encoding="utf-8",
        )
        failures = []
        for fixture, expected in EXPECTED.items():
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCANNER),
                    "--local",
                    str(ROOT / "examples" / "fixtures" / fixture),
                    "--installed-json",
                    str(inventory),
                    "--json",
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            if result.returncode != 0:
                failures.append(f"{fixture}: scanner failed: {result.stderr.strip()}")
                continue
            decision = json.loads(result.stdout)["reports"][0]["decision"]
            if decision != expected:
                failures.append(f"{fixture}: expected {expected}, got {decision}")
        if failures:
            for failure in failures:
                print(failure)
            return 1
    print("fixture_check: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
