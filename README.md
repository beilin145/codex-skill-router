# Codex Skill Router

Opinionated routing rules for Codex skills.

This project adds a small meta-skill that Codex reads before choosing other skills. It turns "several skills match this request" into an explicit routing decision: which skill wins by default, which skills are platform-specific, which skills are duplicate fallbacks, and which third-party skills need a safety review before use.

It also includes a `skill-intake` workflow for evaluating GitHub-hosted skills before installing them.

## What This Is

- `_skill-router`: a Codex skill that acts as a routing table and conflict resolver.
- `skill-intake`: a Codex skill and static scanner for proposed third-party skills.
- Documentation for installing, forcing router-first behavior, and safely reviewing skill repos.

## What This Is Not

- It is not a kernel-level policy engine.
- It does not prevent Codex from making mistakes if the router is not loaded.
- It does not execute or sandbox third-party skills.
- It does not automatically trust GitHub repositories.

The reliable pattern is:

```text
global Codex instruction -> read _skill-router first -> route to the best business skill
```

## Install

Clone or download this repository, then copy the skills into your Codex skills directory:

```bash
./scripts/install.sh
```

Restart Codex after installing new skills so the skill list refreshes.

## Make Router-First Behavior Sticky

Add an equivalent global/developer instruction to your Codex setup:

```text
At the start of every turn, before selecting, reading, invoking, installing, editing, or comparing any skill, read ~/.codex/skills/_skill-router/SKILL.md and follow its routing table.
```

The `_skill-router` description is also written to trigger broadly, but an explicit global instruction is the stronger setup.

## Use

Ask normal questions:

```text
帮我做一个汇报 PPT
```

The router says ordinary PPT/deck work should use `ppt-master`, while Canva and built-in `presentations` are explicit-platform routes only.

Evaluate a skill repo before installing:

```text
评估 https://github.com/owner/repo/tree/main/skills/foo，看看是否应该加入我的 skills
```

`skill-intake` will inspect the repo without executing downloaded code, report prompt-injection and local-execution risks, compare it against installed skills, and classify it as install-candidate, manual-review, duplicate/defer, or reject.

## Project Layout

```text
skills/
  _skill-router/
    SKILL.md
    agents/openai.yaml
  skill-intake/
    SKILL.md
    agents/openai.yaml
    scripts/intake_github_skill.py
docs/
  ROUTING.md
  SECURITY.md
  INTAKE.md
  PUBLISHING.md
examples/
  intake-report.md
scripts/
  install.sh
```

## Safety Model

Third-party skills are prompts plus optional files. Treat them as executable influence over your agent. This project recommends a default-deny intake process:

1. Download or inspect the repo.
2. Do not execute its scripts.
3. Scan `SKILL.md` and directly referenced files.
4. Check for prompt override, secrecy, exfiltration, destructive shell, persistence, package-manager execution, hidden files, symlinks, and executable bits.
5. Compare with installed skills.
6. Install only if the skill adds real value and the risk is acceptable.

See [docs/SECURITY.md](docs/SECURITY.md) for the full checklist.

## License

MIT. See [LICENSE](LICENSE).
