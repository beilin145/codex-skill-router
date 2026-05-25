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
6. Ask the user before installing third-party skills unless the repo is already trusted by local policy.
7. Install approved skills with Codex's system `skill-installer`.
8. Update `_skill-router` with the final route decision.
9. Tell the user to restart Codex after installation.

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

## V0.2 Report Outputs

Each candidate report includes:

- `decision_record`: counts of blocking findings, warnings, duplicate matches, and whether the skill is safe to route by default.
- `install_plan`: an installer command when the source is a GitHub repo and the decision allows possible installation.
- `router_suggestion`: a draft router section, route entry, note, and patch text.

The scanner never installs a skill by itself. `manual-review` and `explicit-only` candidates still require a human decision before installation.

## After Install

Add a router rule only after installation succeeds and the installed skill name is confirmed. Folder names and frontmatter names sometimes differ.

Use this shape:

```markdown
- Specific trigger / platform / file format -> `skill-name`
```

If the skill is weaker than existing skills, add it under "Demoted or Duplicate Skills" instead of making it a default route.

If the report says `reject`, do not install or route it. Keep the finding in private notes only if you need an audit trail.
