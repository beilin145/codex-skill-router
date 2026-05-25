#!/usr/bin/env python3
"""Maintain a local registry of skill-intake decisions."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path


SCHEMA_VERSION = 1


class RegistryError(RuntimeError):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Record and inspect skill-intake decisions.")
    parser.add_argument("--registry", help="Registry JSON path. Defaults to $CODEX_HOME/skills/_skill-router/skill-registry.json.")
    subcommands = parser.add_subparsers(dest="command", required=True)

    record = subcommands.add_parser("record", help="Record decisions from an intake JSON report.")
    record.add_argument("--intake-json", required=True, help="JSON report produced by intake_github_skill.py.")
    record.add_argument("--candidate", action="append", default=[], help="Candidate skill name to record. Can repeat.")

    list_cmd = subcommands.add_parser("list", help="List registry entries.")
    list_cmd.add_argument("--decision", action="append", default=[], help="Filter by decision. Can repeat.")
    list_cmd.add_argument("--tier", action="append", default=[], help="Filter by curated tier. Can repeat.")
    list_cmd.add_argument("--json", action="store_true", help="Print JSON instead of a table.")

    curate = subcommands.add_parser("curate", help="Print a curated-list view grouped by tier.")
    curate.add_argument("--json", action="store_true", help="Print JSON instead of Markdown.")

    show = subcommands.add_parser("show", help="Show one registry entry.")
    show.add_argument("name", help="Skill name.")
    show.add_argument("--json", action="store_true", help="Print JSON instead of Markdown.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        registry_path = Path(args.registry).expanduser() if args.registry else default_registry_path()
        if args.command == "record":
            intake = load_json(Path(args.intake_json))
            registry = load_registry(registry_path)
            reports = selected_reports(intake, set(args.candidate))
            for report in reports:
                upsert_entry(registry, intake, report)
            write_registry(registry_path, registry)
            print(f"recorded {len(reports)} decision(s) in {registry_path}")
        elif args.command == "list":
            registry = load_registry(registry_path)
            entries = list(registry.get("entries", {}).values())
            decisions = set(args.decision)
            if decisions:
                entries = [item for item in entries if item.get("decision") in decisions]
            tiers = set(args.tier)
            if tiers:
                entries = [item for item in entries if item.get("tier") in tiers]
            entries.sort(key=lambda item: (str(item.get("decision", "")), str(item.get("name", ""))))
            if args.json:
                print(json.dumps(entries, indent=2, ensure_ascii=False))
            else:
                print(render_list(entries))
        elif args.command == "curate":
            registry = load_registry(registry_path)
            entries = list(registry.get("entries", {}).values())
            if args.json:
                print(json.dumps(group_by_tier(entries), indent=2, ensure_ascii=False))
            else:
                print(render_curated(entries))
        elif args.command == "show":
            registry = load_registry(registry_path)
            entry = registry.get("entries", {}).get(args.name)
            if not entry:
                raise RegistryError(f"skill not found in registry: {args.name}")
            if args.json:
                print(json.dumps(entry, indent=2, ensure_ascii=False))
            else:
                print(render_show(entry))
    except RegistryError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


def default_registry_path() -> Path:
    codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).expanduser()
    return codex_home / "skills" / "_skill-router" / "skill-registry.json"


def now_utc() -> str:
    return dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def load_json(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise RegistryError(f"JSON not found: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RegistryError(f"invalid JSON: {exc}") from exc


def load_registry(path: Path) -> dict[str, object]:
    if not path.exists():
        return {"schema_version": SCHEMA_VERSION, "entries": {}}
    registry = load_json(path)
    if not isinstance(registry.get("entries"), dict):
        raise RegistryError("registry missing entries object")
    return registry


def write_registry(path: Path, registry: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    registry["schema_version"] = SCHEMA_VERSION
    path.write_text(json.dumps(registry, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def selected_reports(intake: dict[str, object], names: set[str]) -> list[dict[str, object]]:
    raw_reports = intake.get("reports")
    if not isinstance(raw_reports, list):
        raise RegistryError("intake JSON missing reports array")
    reports = [item for item in raw_reports if isinstance(item, dict)]
    if names:
        reports = [item for item in reports if str(item.get("name", "")) in names]
        missing = names - {str(item.get("name", "")) for item in reports}
        if missing:
            raise RegistryError(f"candidate(s) not found in report: {', '.join(sorted(missing))}")
    if not reports:
        raise RegistryError("no candidate reports selected")
    return reports


def upsert_entry(registry: dict[str, object], intake: dict[str, object], report: dict[str, object]) -> None:
    entries = registry.setdefault("entries", {})
    if not isinstance(entries, dict):
        raise RegistryError("registry entries is not an object")
    name = str(report.get("name") or "unknown-skill")
    previous = entries.get(name, {}) if isinstance(entries.get(name), dict) else {}
    created_at = previous.get("created_at") or now_utc()
    router = report.get("router_suggestion") if isinstance(report.get("router_suggestion"), dict) else {}
    install_plan = report.get("install_plan") if isinstance(report.get("install_plan"), dict) else {}
    capability_profile = report.get("capability_profile") if isinstance(report.get("capability_profile"), dict) else {}
    decision = str(report.get("decision") or "manual-review")
    entries[name] = {
        "name": name,
        "decision": decision,
        "tier": tier_for_decision(decision),
        "path": str(report.get("path") or ""),
        "source": str(intake.get("source") or report.get("source") or ""),
        "repo": intake.get("repo"),
        "ref": intake.get("ref"),
        "sha256": str(report.get("sha256") or ""),
        "description": str(report.get("description") or ""),
        "rationale": report.get("rationale") if isinstance(report.get("rationale"), list) else [],
        "duplicate_matches": report.get("duplicate_matches") if isinstance(report.get("duplicate_matches"), list) else [],
        "capability_profile": capability_profile,
        "router_patch": str(router.get("patch") or ""),
        "router_section": str(router.get("section") or ""),
        "install_command": install_plan.get("command"),
        "created_at": created_at,
        "updated_at": now_utc(),
    }


def tier_for_decision(decision: str) -> str:
    return {
        "install-candidate": "core-or-candidate",
        "explicit-only": "explicit-platform",
        "manual-review": "watch",
        "defer-duplicate": "duplicate",
        "reject": "rejected",
    }.get(decision, "watch")


def render_list(entries: list[object]) -> str:
    if not entries:
        return "No registry entries."
    lines = ["| Skill | Decision | Tier | Path | Source |", "|---|---|---|---|---|"]
    for raw in entries:
        entry = raw if isinstance(raw, dict) else {}
        lines.append(
            f"| `{escape(str(entry.get('name', '')))}` | `{escape(str(entry.get('decision', '')))}` | "
            f"`{escape(str(entry.get('tier', '')))}` | "
            f"`{escape(str(entry.get('path', '')))}` | `{escape(str(entry.get('source', '')))}` |"
        )
    return "\n".join(lines)


def render_show(entry: dict[str, object]) -> str:
    lines = [
        f"# `{entry.get('name', '')}`",
        "",
        f"- Decision: `{entry.get('decision', '')}`",
        f"- Tier: `{entry.get('tier', '')}`",
        f"- Path: `{entry.get('path', '')}`",
        f"- Source: `{entry.get('source', '')}`",
        f"- SHA-256: `{entry.get('sha256', '')}`",
        f"- Router section: `{entry.get('router_section', '')}`",
        f"- Created: `{entry.get('created_at', '')}`",
        f"- Updated: `{entry.get('updated_at', '')}`",
        "",
        "## Router Patch",
        "",
        "```markdown",
        str(entry.get("router_patch") or ""),
        "```",
    ]
    if entry.get("install_command"):
        lines.extend(["", "## Install Command", "", "```bash", str(entry["install_command"]), "```"])
    profile = entry.get("capability_profile") if isinstance(entry.get("capability_profile"), dict) else {}
    if profile:
        lines.extend(["", "## Capability Profile", ""])
        for key in ["domains", "inputs", "outputs", "tool_dependencies", "safety_shape"]:
            values = profile.get(key) if isinstance(profile.get(key), list) else []
            rendered = ", ".join(f"`{value}`" for value in values) if values else "(none detected)"
            lines.append(f"- {key.replace('_', ' ').title()}: {rendered}")
    return "\n".join(lines)


def group_by_tier(entries: list[object]) -> dict[str, list[object]]:
    groups: dict[str, list[object]] = {
        "core-or-candidate": [],
        "explicit-platform": [],
        "watch": [],
        "duplicate": [],
        "rejected": [],
    }
    for raw in entries:
        entry = raw if isinstance(raw, dict) else {}
        tier = str(entry.get("tier") or tier_for_decision(str(entry.get("decision") or "")))
        groups.setdefault(tier, []).append(entry)
    for items in groups.values():
        items.sort(key=lambda item: str(item.get("name", "")))
    return groups


def render_curated(entries: list[object]) -> str:
    groups = group_by_tier(entries)
    labels = {
        "core-or-candidate": "Core Or Candidate",
        "explicit-platform": "Explicit Platform",
        "watch": "Watch",
        "duplicate": "Duplicate",
        "rejected": "Rejected",
    }
    lines = ["# Skill Registry Curated List", ""]
    for tier, title in labels.items():
        lines.append(f"## {title}")
        lines.append("")
        items = groups.get(tier, [])
        if not items:
            lines.append("- None recorded.")
        else:
            for item in items:
                lines.append(f"- `{item.get('name')}`: `{item.get('decision')}` ({item.get('path')})")
        lines.append("")
    return "\n".join(lines).rstrip()


def escape(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


if __name__ == "__main__":
    raise SystemExit(main())
