# Example Skill Intake Report

Source: `https://github.com/example/skills/tree/main/skills/foo`

| Skill | Decision | Why |
|---|---|---|
| `foo` | `manual-review` | No prompt-injection blocker found, but the skill includes executable scripts and package-manager commands. |

Recommended router entry:

```markdown
- Explicit Foo platform workflow -> `foo`; keep existing generic skills as the default for non-Foo work.
```

Recommended install step after user approval:

```bash
python3 ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py \
  --repo example/skills \
  --path skills/foo
```
