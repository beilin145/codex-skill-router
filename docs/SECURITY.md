# Security Checklist

Skills are instructions. A malicious or careless skill can steer Codex toward unsafe behavior even when it does not contain traditional executable malware.

## Red Flags

Reject or quarantine a skill if it instructs Codex to:

- Ignore, override, bypass, or hide higher-priority instructions.
- Conceal behavior from the user.
- Read unrelated private paths.
- Exfiltrate secrets, tokens, SSH keys, browser profiles, or environment variables.
- Upload local files without an explicit user request.
- Install persistence through shell startup files, launch agents, cron, systemd, browser extensions, or background services.
- Run destructive commands such as `rm -rf`, disk wipes, forced resets, or mass deletes without explicit user approval.
- Pipe remote content into a shell, for example `curl | sh`.
- Execute package-manager or remote-code commands as a normal usage path without explaining the supply-chain risk.

## Files To Inspect

For every third-party skill, inspect:

- `SKILL.md`
- directly referenced scripts, references, and assets
- `agents/openai.yaml`
- hidden files
- symlinks
- executable files
- notebooks
- SVG and HTML assets
- large files that hide content from quick review

## Intake Decisions

Use these decision labels:

- `install-candidate`: no blocker found, adds useful capability, not clearly covered by a better installed skill.
- `manual-review`: no definite blocker, but scripts, package-manager commands, platform credentials, or broad permissions need a human decision.
- `defer-duplicate`: mostly covered by stronger installed skills.
- `explicit-only`: useful only when the user names the exact platform/tool/workflow.
- `reject`: prompt-injection, exfiltration, persistence, destructive behavior, or unacceptable policy risk.

## Important Limitation

Static scanning reduces risk; it does not prove a skill is safe. A clean report means "no obvious issue found in inspected files", not "trusted forever".

Re-run intake after upstream changes.
