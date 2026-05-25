#!/usr/bin/env python3
"""Apply skill-intake JSON decisions to the managed router section.

The script only edits the bounded managed section in _skill-router/SKILL.md.
It does not install skills and it does not execute candidate code.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


START_MARKER = "<!-- skill-router-managed:start -->"
END_MARKER = "<!-- skill-router-managed:end -->"


class ApplyError(RuntimeError):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply skill-intake decisions to _skill-router.")
    parser.add_argument("--intake-json", required=True, help="JSON report produced by intake_github_skill.py.")
    parser.add_argument("--router", help="Router SKILL.md path. Defaults to $CODEX_HOME/skills/_skill-router/SKILL.md.")
    parser.add_argument("--candidate", action="append", default=[], help="Candidate skill name to apply. Can repeat.")
    parser.add_argument("--registry", help="Also record selected decisions in this registry JSON path.")
    parser.add_argument("--apply", action="store_true", help="Write the router file. Without this, print the proposed managed section.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        intake = load_json(Path(args.intake_json))
        router_path = Path(args.router).expanduser() if args.router else default_router_path()
        reports = selected_reports(intake, set(args.candidate))
        router_text = router_path.read_text(encoding="utf-8") if router_path.exists() else ""
        existing = parse_existing_entries(router_text)
        entries = merge_entries(existing, build_entries(intake, reports))
        managed_section = render_managed_section(entries)
        if args.apply:
            if not router_text:
                raise ApplyError(f"router file not found: {router_path}")
            updated = replace_managed_section(router_text, managed_section)
            if args.registry:
                record_registry(args.intake_json, args.registry, args.candidate)
            router_path.write_text(updated, encoding="utf-8")
            print(f"updated router: {router_path}")
        else:
            print(managed_section)
    except ApplyError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


def record_registry(intake_json: str, registry: str, candidates: list[str]) -> None:
    script = Path(__file__).with_name("skill_registry.py")
    command = [sys.executable, str(script), "--registry", registry, "record", "--intake-json", intake_json]
    for candidate in candidates:
        command.extend(["--candidate", candidate])
    result = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        raise ApplyError(result.stderr.strip() or "failed to record registry")
    print(result.stdout.strip())


def default_router_path() -> Path:
    codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).expanduser()
    return codex_home / "skills" / "_skill-router" / "SKILL.md"


def load_json(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise ApplyError(f"intake JSON not found: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ApplyError(f"invalid intake JSON: {exc}") from exc


def selected_reports(intake: dict[str, object], names: set[str]) -> list[dict[str, object]]:
    raw_reports = intake.get("reports")
    if not isinstance(raw_reports, list):
        raise ApplyError("intake JSON missing reports array")
    reports = [item for item in raw_reports if isinstance(item, dict)]
    if names:
        reports = [item for item in reports if str(item.get("name", "")) in names]
        missing = names - {str(item.get("name", "")) for item in reports}
        if missing:
            raise ApplyError(f"candidate(s) not found in report: {', '.join(sorted(missing))}")
    if not reports:
        raise ApplyError("no candidate reports selected")
    return reports


def empty_groups() -> dict[str, list[str]]:
    return {
        "Default Routes": [],
        "Explicit Only": [],
        "Demoted or Duplicate": [],
        "Rejected or Quarantined": [],
        "Manual Review": [],
    }


def build_entries(intake: dict[str, object], reports: list[dict[str, object]]) -> dict[str, str]:
    entries: dict[str, str] = {}
    for report in reports:
        decision = str(report.get("decision", "manual-review"))
        name = str(report.get("name", "unknown-skill"))
        router = report.get("router_suggestion") if isinstance(report.get("router_suggestion"), dict) else {}
        patch = str(router.get("patch") or f"- Review `{name}` before routing.")
        note = str(router.get("note") or "")
        source = str(intake.get("source") or report.get("source") or "unknown source")
        line = patch
        details = compact_details(report, source, note)
        if details:
            line = f"{line} ({details})"

        if decision == "install-candidate":
            group = "Default Routes"
        elif decision == "explicit-only":
            group = "Explicit Only"
        elif decision == "defer-duplicate":
            group = "Demoted or Duplicate"
        elif decision == "reject":
            group = "Rejected or Quarantined"
        else:
            group = "Manual Review"
        entries[name] = f"{group}\t{line}"
    return entries


def parse_existing_entries(router_text: str) -> dict[str, str]:
    section = extract_managed_section(router_text)
    if not section:
        return {}
    entries: dict[str, str] = {}
    current_group = ""
    for raw_line in section.splitlines():
        line = raw_line.rstrip()
        if line.startswith("### "):
            current_group = line.removeprefix("### ").strip()
            continue
        if not current_group or not line.startswith("- ") or line == "- None recorded.":
            continue
        key = extract_entry_key(line)
        entries[key] = f"{current_group}\t{line}"
    return entries


def extract_managed_section(text: str) -> str:
    start = text.find(START_MARKER)
    end = text.find(END_MARKER)
    if start == -1 or end == -1 or end < start:
        return ""
    return text[start + len(START_MARKER) : end]


def extract_entry_key(line: str) -> str:
    marker = "-> `"
    if marker in line:
        return line.split(marker, 1)[1].split("`", 1)[0]
    if line.startswith("- `"):
        return line.split("`", 2)[1]
    return line


def merge_entries(existing: dict[str, str], incoming: dict[str, str]) -> dict[str, list[str]]:
    merged = dict(existing)
    merged.update(incoming)
    groups = empty_groups()
    for value in merged.values():
        group, line = value.split("\t", 1)
        groups.setdefault(group, []).append(line)
    return groups


def render_managed_section(groups: dict[str, list[str]]) -> str:
    lines = [
        START_MARKER,
        "## Managed Skill Intake Decisions",
        "",
        "This section is maintained by `skill-intake/scripts/apply_intake_decision.py`.",
        "Manual edits inside the markers may be overwritten; edit the fixed router rules outside this block for permanent policy.",
        "",
    ]
    for title, entries in groups.items():
        lines.append(f"### {title}")
        lines.append("")
        if entries:
            lines.extend(sorted(entries, key=str.casefold))
        else:
            lines.append("- None recorded.")
        lines.append("")
    lines.append(END_MARKER)
    return "\n".join(lines).rstrip()


def compact_details(report: dict[str, object], source: str, note: str) -> str:
    parts: list[str] = []
    path = str(report.get("path") or "")
    sha256 = str(report.get("sha256") or "")
    if path:
        parts.append(f"path: `{path}`")
    if sha256:
        parts.append(f"sha256: `{sha256[:12]}`")
    if source and source != "unknown source":
        parts.append(f"source: `{source}`")
    if note:
        parts.append(note)
    return "; ".join(parts)


def replace_managed_section(text: str, managed_section: str) -> str:
    start = text.find(START_MARKER)
    end = text.find(END_MARKER)
    if start == -1 and end == -1:
        anchor = "\n## Final Tie Breakers\n"
        if anchor not in text:
            raise ApplyError("router has no managed markers and no Final Tie Breakers anchor")
        return text.replace(anchor, f"\n{managed_section}\n{anchor}", 1)
    if start == -1 or end == -1 or end < start:
        raise ApplyError("router managed markers are malformed")
    end += len(END_MARKER)
    return f"{text[:start].rstrip()}\n\n{managed_section}\n\n{text[end:].lstrip()}"


if __name__ == "__main__":
    raise SystemExit(main())
