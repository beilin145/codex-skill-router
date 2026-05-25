# Skill Intake Workflow

The intake workflow answers one question:

```text
Should this GitHub skill be installed, routed, demoted, or rejected?
```

## Agent Workflow

1. Read `_skill-router` first.
2. Load `skill-intake`.
3. Run the static scanner against the GitHub repo, URL, or local directory.
4. Review the Markdown or JSON report.
5. Use the generated install plan and router patch suggestion as drafts.
6. Apply accepted routing decisions to `_skill-router` with the managed-section updater.
7. Ask the user before installing third-party skills unless the repo is already trusted by local policy.
8. Install approved skills with Codex's system `skill-installer`.
9. Tell the user to restart Codex after installation or router updates.

## Scanner Examples

Evaluate one GitHub skill path:

```bash
python3 skills/skill-intake/scripts/intake_github_skill.py \
  --repo owner/repo \
  --ref main \
  --path skills/foo
```

Evaluate every skill in a repo:

```bash
python3 skills/skill-intake/scripts/intake_github_skill.py \
  --repo owner/repo
```

Evaluate a local checkout:

```bash
python3 skills/skill-intake/scripts/intake_github_skill.py \
  --local /path/to/repo \
  --path skills/foo
```

Write Markdown and JSON reports:

```bash
python3 skills/skill-intake/scripts/intake_github_skill.py \
  --url https://github.com/owner/repo/tree/main/skills/foo \
  --out intake-reports/foo.intake.md \
  --json-out intake-reports/foo.intake.json
```

Write only router patch suggestions:

```bash
python3 skills/skill-intake/scripts/intake_github_skill.py \
  --url https://github.com/owner/repo/tree/main/skills/foo \
  --router-out intake-reports/foo.router.md
```

Preview router managed-section updates:

```bash
python3 skills/skill-intake/scripts/apply_intake_decision.py \
  --intake-json intake-reports/foo.intake.json
```

Apply accepted routing decisions:

```bash
python3 skills/skill-intake/scripts/apply_intake_decision.py \
  --intake-json intake-reports/foo.intake.json \
  --router skills/_skill-router/SKILL.md \
  --apply
```

## V0.2 Report Outputs

Each candidate report includes:

- `decision_record`: counts of blocking findings, warnings, duplicate matches, and whether the skill is safe to route by default.
- `install_plan`: an installer command when the source is a GitHub repo and the decision allows possible installation.
- `router_suggestion`: a draft router section, route entry, note, and patch text.

The scanner never installs a skill by itself. `manual-review` and `explicit-only` candidates still require a human decision before installation.

## V0.3 Router Automation

`apply_intake_decision.py` reads the V0.2 JSON report and updates only the bounded managed section in `_skill-router/SKILL.md`.

It groups candidates into:

- `Default Routes`
- `Explicit Only`
- `Demoted or Duplicate`
- `Rejected or Quarantined`
- `Manual Review`

It does not install skills, execute candidate code, or rewrite the fixed hand-authored router sections.

## After Install

Add a router rule only after installation succeeds and the installed skill name is confirmed. Folder names and frontmatter names sometimes differ.

Use this shape:

```markdown
- Specific trigger / platform / file format -> `skill-name`
```

If the skill is weaker than existing skills, add it under "Demoted or Duplicate Skills" instead of making it a default route.

If the report says `reject`, do not install or route it. Keep the finding in private notes only if you need an audit trail.
