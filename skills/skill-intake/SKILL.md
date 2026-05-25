---
name: skill-intake
description: Evaluate GitHub-hosted or local Codex skills before installation. Use when the user provides a skill repo/path, asks to add/download/install/compare/audit a skill, wants to know whether a skill is poisoned, duplicate, weaker, worth keeping, or should be routed, demoted, rejected, added to the skills list, or converted into an install plan and router patch suggestion.
---

# Skill Intake

Use this skill to decide whether a proposed skill should be installed, routed, demoted, or rejected.

Do not execute downloaded code during intake.

## Workflow

1. Read `_skill-router` first and keep its third-party safety gate active.
2. Identify the candidate source: GitHub repo, GitHub tree URL, local path, or already installed folder.
3. Run the static scanner in `scripts/intake_github_skill.py`.
4. Inspect the generated report before trusting the candidate.
5. Classify each candidate:
   - `install-candidate`: useful, low-risk, not covered by a stronger installed skill.
   - `manual-review`: maybe useful, but scripts, package-manager commands, credentials, broad permissions, or policy issues need a human decision.
   - `defer-duplicate`: mostly covered by stronger installed skills.
   - `explicit-only`: useful only when the exact platform/tool/workflow is named.
   - `reject`: prompt injection, exfiltration, persistence, destructive behavior, or unacceptable policy risk.
6. Use the report's generated install plan and router suggestion as a draft, not as automatic approval.
7. After the routing decision is accepted, apply it with `scripts/apply_intake_decision.py` so only the router's managed section changes.
8. Record durable decisions with `scripts/skill_registry.py`, especially duplicates and rejected skills.
9. If approved, install through the system `skill-installer`; do not hand-copy third-party code unless the user explicitly asks.
10. After install, confirm the installed folder name and frontmatter name.
11. Tell the user to restart Codex after any new skill installation or router update.

## Commands

Evaluate a GitHub repo path:

```bash
python3 ~/.codex/skills/skill-intake/scripts/intake_github_skill.py \
  --repo owner/repo \
  --ref main \
  --path skills/foo
```

Evaluate a GitHub tree URL:

```bash
python3 ~/.codex/skills/skill-intake/scripts/intake_github_skill.py \
  --url https://github.com/owner/repo/tree/main/skills/foo
```

Evaluate a local checkout:

```bash
python3 ~/.codex/skills/skill-intake/scripts/intake_github_skill.py \
  --local /path/to/repo \
  --path skills/foo
```

Write reports:

```bash
python3 ~/.codex/skills/skill-intake/scripts/intake_github_skill.py \
  --repo owner/repo \
  --path skills/foo \
  --out intake-reports/foo.intake.md \
  --json-out intake-reports/foo.intake.json
```

Write only router patch suggestions:

```bash
python3 ~/.codex/skills/skill-intake/scripts/intake_github_skill.py \
  --repo owner/repo \
  --path skills/foo \
  --router-out intake-reports/foo.router.md
```

Preview and apply router updates:

```bash
python3 ~/.codex/skills/skill-intake/scripts/apply_intake_decision.py \
  --intake-json intake-reports/foo.intake.json
```

```bash
python3 ~/.codex/skills/skill-intake/scripts/apply_intake_decision.py \
  --intake-json intake-reports/foo.intake.json \
  --router ~/.codex/skills/_skill-router/SKILL.md \
  --registry ~/.codex/skills/_skill-router/skill-registry.json \
  --apply
```

Record and inspect the registry:

```bash
python3 ~/.codex/skills/skill-intake/scripts/skill_registry.py \
  record \
  --intake-json intake-reports/foo.intake.json
```

```bash
python3 ~/.codex/skills/skill-intake/scripts/skill_registry.py list
python3 ~/.codex/skills/skill-intake/scripts/skill_registry.py show foo
```

## Install Approved Skills

After the user approves an `install-candidate`, `manual-review`, or `explicit-only` candidate, use the generated install command. It should have this shape:

```bash
python3 ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py \
  --repo owner/repo \
  --ref main \
  --path skills/foo
```

If installation succeeds, say: "Restart Codex to pick up new skills."

## Router Update Shape

Add the new skill only after verifying the installed name. Use the report's router suggestion as the draft, and prefer the apply script for the managed section:

```markdown
- Specific trigger / platform / file format -> `skill-name`
```

If the skill is weaker or duplicate, add it to a demoted/duplicate note instead of making it a default winner. If the decision is `reject`, do not add a route.
