# Skill Governance

This project treats skills as a small governed inventory, not an ever-growing prompt pile.

## Standard Intake Pipeline

For every proposed skill repo or path:

1. Run `skill-intake`.
2. Review safety findings and capability overlap.
3. Record the decision in the registry.
4. Apply accepted routing decisions to the router managed section.
5. Install only approved candidates.
6. Restart Codex after installing or updating router rules.

Use the workflow helper:

```bash
python3 skills/skill-intake/scripts/intake_workflow.py \
  --url https://github.com/owner/repo/tree/main/skills/foo \
  --record-registry \
  --apply-router
```

Add `--install-approved` only after you agree to install approved candidates.

## Keep / Demote / Reject Standards

Use `install-candidate` when:

- No blocking safety findings exist.
- The skill has a clear capability not already covered by a stronger installed skill.
- The trigger is broad enough to deserve default routing, or the skill is the obvious best specialist for its domain.
- The files are small enough to review, or large assets are expected and justified.

Use `explicit-only` when:

- The skill is useful only for a named platform, vendor, tool, or niche workflow.
- A stronger generic/default skill should handle normal requests.
- The skill depends on credentials, cloud tools, or side effects that should not run unless named.

Use `defer-duplicate` when:

- A same-name skill is already installed.
- A stronger installed skill covers the same inputs, outputs, and workflow.
- The candidate adds examples or wording but no meaningful new tool, artifact, or domain ability.

Use `manual-review` when:

- There are warnings but no blocker.
- The skill uses package managers, network clients, browser automation, credentials, large assets, or executable helpers.
- The value is plausible but the overlap needs human judgment.

Use `reject` when:

- It tries to override higher-priority instructions.
- It hides behavior from the user.
- It exfiltrates secrets or unrelated private files.
- It installs persistence, changes startup files, or runs destructive commands.
- It requires broad, unjustified remote execution as a normal path.

## Curated Tiers

The registry maps decisions to operational tiers:

| Tier | Meaning |
|---|---|
| `core-or-candidate` | Possible default winner after review/install. |
| `explicit-platform` | Use only when the user names the exact platform/tool/workflow. |
| `watch` | Keep under manual review; do not route automatically. |
| `duplicate` | Covered by installed skills; do not install by default. |
| `rejected` | Do not install or route. |

Generate a curated list:

```bash
python3 skills/skill-intake/scripts/skill_registry.py \
  --registry skill-registry.json \
  curate
```

## Capability Comparison

V0.5 reports include a `capability_profile` with:

- domains
- inputs
- outputs
- tool dependencies
- safety shape
- closest installed overlap

Use this profile to answer "which skill is better for this exact task?" instead of relying only on name similarity.

## Calibration Fixtures

The `examples/fixtures/` directory contains minimal local skills for scanner calibration:

| Fixture | Expected purpose |
|---|---|
| `safe-new` | Clean candidate with no installed overlap. |
| `explicit-platform` | Platform-specific skill that should be routed narrowly. |
| `duplicate` | Same-name duplicate behavior. |
| `manual-review` | Package-manager warning behavior. |
| `reject` | Blocking prompt-injection/exfiltration behavior. |

These fixtures are not recommendations to install. They exist so release checks can exercise the intake categories.

Run fixture calibration:

```bash
python3 scripts/fixture_check.py
```
