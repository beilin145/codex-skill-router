#!/usr/bin/env sh
set -eu

CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
SKILLS_DIR="$CODEX_HOME/skills"
REPO_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"

mkdir -p "$SKILLS_DIR"
mkdir -p "$SKILLS_DIR/_skill-router" "$SKILLS_DIR/skill-intake"
cp -R "$REPO_DIR/skills/_skill-router/." "$SKILLS_DIR/_skill-router/"
cp -R "$REPO_DIR/skills/skill-intake/." "$SKILLS_DIR/skill-intake/"

cat <<'MSG'
Installed:
- ~/.codex/skills/_skill-router
- ~/.codex/skills/skill-intake

Restart Codex to pick up new skills.

For best routing, add a global/developer instruction equivalent to:
At the start of every turn, before selecting, reading, invoking, installing,
editing, or comparing any skill, read ~/.codex/skills/_skill-router/SKILL.md.
MSG
