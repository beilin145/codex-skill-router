# Skill Intake Workflow

The intake workflow answers one question:

```text
Should this GitHub skill be installed, routed, demoted, or rejected?
```

## Agent Workflow

1. Read `_skill-router` first.
2. Load `skill-intake`.
3. Run the static scanner against the GitHub repo, URL, or local directory.
4. Review the report.
5. If the decision is `install-candidate`, ask the user before installing third-party skills unless the repo is already trusted by local policy.
6. Install approved skills with Codex's system `skill-installer`.
7. Update `_skill-router` with the final route decision.
8. Tell the user to restart Codex after installation.

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

## After Install

Add a router rule only after installation succeeds and the installed skill name is confirmed. Folder names and frontmatter names sometimes differ.

Use this shape:

```markdown
- Specific trigger / platform / file format -> `skill-name`
```

If the skill is weaker than existing skills, add it under "Demoted or Duplicate Skills" instead of making it a default route.
