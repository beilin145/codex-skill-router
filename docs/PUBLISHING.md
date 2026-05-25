# Publishing Checklist

Use this before pushing the project to a public GitHub repository.

## Required Files

- `README.md`
- `LICENSE`
- `.gitignore`
- `skills/_skill-router/SKILL.md`
- `skills/_skill-router/agents/openai.yaml`
- `skills/skill-intake/SKILL.md`
- `skills/skill-intake/scripts/intake_github_skill.py`
- `skills/skill-intake/agents/openai.yaml`
- `docs/ROUTING.md`
- `docs/SECURITY.md`
- `docs/INTAKE.md`

## Local Checks

```bash
find . -name SKILL.md -print
python3 -B -c 'import ast, pathlib; ast.parse(pathlib.Path("skills/skill-intake/scripts/intake_github_skill.py").read_text())'
python3 -B skills/skill-intake/scripts/intake_github_skill.py --local . --path skills/skill-intake
python3 -B skills/skill-intake/scripts/intake_github_skill.py --local . --path skills/_skill-router
python3 scripts/release_check.py
```

Expected:

- `skill-intake` reports no safety findings for itself.
- `_skill-router` may report a same-name duplicate if already installed locally; that is expected.
- No private paths or secrets are found in tracked public files.

## Do Not Publish By Accident

`github-skill-hunt.md` is ignored by `.gitignore` because it is a local research log and may contain machine-specific paths or temporary notes. Publish a cleaned summary instead if you want to share the research.

## Suggested GitHub Description

```text
Opinionated Codex skills router plus safe intake workflow for third-party skills.
```
