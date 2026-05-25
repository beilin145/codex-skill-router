# Example Standard Intake Workflow

This example shows the V0.5 flow for a proposed skill:

```bash
python3 skills/skill-intake/scripts/intake_workflow.py \
  --url https://github.com/example/skills/tree/main/skills/foo \
  --work-dir intake-reports/foo \
  --registry skill-registry.json \
  --router skills/_skill-router/SKILL.md \
  --record-registry \
  --apply-router
```

Generated files:

- `intake-reports/foo/intake.md`
- `intake-reports/foo/intake.json`
- `intake-reports/foo/router.md`
- `skill-registry.json`

Review before installing:

```bash
python3 skills/skill-intake/scripts/skill_registry.py \
  --registry skill-registry.json \
  show foo
```

Curated view:

```bash
python3 skills/skill-intake/scripts/skill_registry.py \
  --registry skill-registry.json \
  curate
```

Only after approving installation:

```bash
python3 skills/skill-intake/scripts/intake_workflow.py \
  --url https://github.com/example/skills/tree/main/skills/foo \
  --work-dir intake-reports/foo \
  --registry skill-registry.json \
  --router skills/_skill-router/SKILL.md \
  --record-registry \
  --apply-router \
  --install-approved
```
