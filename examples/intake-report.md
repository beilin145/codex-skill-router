# Example Skill Intake Report

- Source: `https://github.com/example/skills/tree/main`
- Repo: `example/skills`
- Ref: `main`
- Candidates: `1`

## Summary

| Skill | Path | Decision | Files | Findings |
|---|---|---:|---:|---:|
| `foo` | `skills/foo` | `explicit-only` | 4 | 0 |

## `foo`

- Path: `skills/foo`
- Description: Foo platform workflow helper.
- SHA-256 of SKILL.md: `example`
- Size: 4 file(s), 12000 byte(s)
- Decision: `explicit-only`
- Rationale:
  - Some overlap with installed skills; route narrowly if installed.

### Installed Skill Overlap

| Kind | Score | Installed Skill | Description |
|---|---:|---|---|
| similar-description | 0.62 | `existing-foo-adjacent` | Existing generic workflow skill. |

### Suggested Next Step

Install only if the exact platform/tool is wanted. Route it as explicit-only, not as a default winner.

### Install Plan

- Eligible: `true`
- Reason: Run only after user approval and after reviewing the report.

```bash
python3 ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py --repo example/skills --ref main --path skills/foo
```

### Router Suggestion

- Section: `Explicit-Only or the matching domain section`
- Note: Route narrowly only when the exact platform/tool/workflow is named.

```markdown
- Explicit foo workflow -> `foo`
```

## Router Patch Suggestions

### `foo`

- Decision: `explicit-only`
- Section: `Explicit-Only or the matching domain section`
- Note: Route narrowly only when the exact platform/tool/workflow is named.
- Overlaps: `existing-foo-adjacent`

```markdown
- Explicit foo workflow -> `foo`
```
