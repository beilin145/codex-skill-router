# Codex Skill Router

Choose the right Codex skill, avoid duplicate skill sprawl, and audit third-party skills before installing them.

Codex skill lists can grow quickly. When several skills match one request, default semantic matching may pick a broad, duplicate, or weaker skill. This project adds a router skill that Codex reads first, so skill selection follows explicit rules instead of guesswork.

It also includes `skill-intake`, a lightweight static intake workflow for evaluating GitHub-hosted skills before they enter your local skill list. Intake reports produce draft install commands and router patch suggestions, and V0.3 can apply accepted decisions into the router's managed section.

## Why Use It

- Prefer a known best skill when several skills match the same request.
- Keep platform-specific routes explicit, such as Canva, Figma, GitHub, Browser, gstack, HyperFrames, PDFs, docs, and sheets.
- Demote duplicate or weaker skills without deleting them.
- Audit third-party `SKILL.md` folders for prompt-injection and local-execution risks before installing.
- Turn a proposed GitHub skill into an install/defer/reject decision, a draft install command, and a router entry suggestion.
- Apply accepted intake decisions to the router without touching hand-authored routing policy.
- Keep public routing defaults separate from your private local overrides.

## Quick Start

```bash
git clone https://github.com/beilin145/codex-skill-router.git
cd codex-skill-router
./scripts/install.sh
```

Then restart Codex.

For best results, add a global/developer instruction equivalent to:

```text
At the start of every turn, before selecting, reading, invoking, installing, editing, or comparing any skill, read ~/.codex/skills/_skill-router/SKILL.md and follow its routing table.
```

## Example

```text
User: 帮我做一个汇报 PPT
Router: use ppt-master by default

User: 用 Canva 做一版 deck
Router: use canva-branded-presentation because Canva was explicit

User: 评估 https://github.com/owner/repo/tree/main/skills/foo
Router: use skill-intake before installing or trusting it
```

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

## Install Details

Clone this repository, then install the skills into your Codex skills directory:

```bash
git clone https://github.com/beilin145/codex-skill-router.git
cd codex-skill-router
./scripts/install.sh
```

If you already cloned the repository and are inside it, just run:

```bash
./scripts/install.sh
```

Restart Codex after installing new skills so the skill list refreshes.

## Update

Pull the latest version and reinstall:

```bash
git pull
./scripts/install.sh
```

Restart Codex after updating installed skills.

## Make Router-First Behavior Sticky

Add an equivalent global/developer instruction to your Codex setup:

```text
At the start of every turn, before selecting, reading, invoking, installing, editing, or comparing any skill, read ~/.codex/skills/_skill-router/SKILL.md and follow its routing table.
```

The `_skill-router` description is also written to trigger broadly, but an explicit global instruction is the stronger setup.

## Usage Notes

Ask normal questions:

```text
帮我做一个汇报 PPT
```

The router says ordinary PPT/deck work should use `ppt-master`, while Canva and built-in `presentations` are explicit-platform routes only.

Evaluate a skill repo before installing:

```text
评估 https://github.com/owner/repo/tree/main/skills/foo，看看是否应该加入我的 skills
```

`skill-intake` will inspect the repo without executing downloaded code, report prompt-injection and local-execution risks, compare it against installed skills, and classify it as install-candidate, manual-review, explicit-only, defer-duplicate, or reject.

For automation, write both human and machine-readable outputs:

```bash
python3 skills/skill-intake/scripts/intake_github_skill.py \
  --repo owner/repo \
  --path skills/foo \
  --out intake-reports/foo.intake.md \
  --json-out intake-reports/foo.intake.json \
  --router-out intake-reports/foo.router.md
```

The report includes a draft installer command for approved candidates and a router patch suggestion for default, explicit-only, duplicate, or rejected outcomes.

Apply an accepted decision to the router's managed section:

```bash
python3 skills/skill-intake/scripts/apply_intake_decision.py \
  --intake-json intake-reports/foo.intake.json \
  --router skills/_skill-router/SKILL.md \
  --apply
```

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

Released under the MIT License. See [LICENSE](LICENSE).
