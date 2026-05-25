#!/usr/bin/env python3
"""Static intake scanner for Codex skills.

The scanner downloads or opens skill folders, inspects text and metadata, and
prints a report. It never executes downloaded code.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import os
import re
import shutil
import shlex
import stat
import sys
import tempfile
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
from typing import Iterable


IGNORE_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    "dist",
    "build",
    ".next",
    ".turbo",
}

TEXT_EXTS = {
    ".md",
    ".txt",
    ".yaml",
    ".yml",
    ".json",
    ".toml",
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".sh",
    ".bash",
    ".zsh",
    ".fish",
    ".html",
    ".svg",
    ".xml",
    ".css",
    ".csv",
}

MAX_TEXT_BYTES = 512_000
LARGE_FILE_BYTES = 200_000
VERY_LARGE_FILE_BYTES = 5_000_000


@dataclasses.dataclass
class RiskRule:
    category: str
    severity: str
    pattern: re.Pattern[str]
    note: str


@dataclasses.dataclass
class RiskMatch:
    category: str
    severity: str
    path: str
    line: int
    text: str
    note: str


@dataclasses.dataclass
class FileFinding:
    category: str
    severity: str
    path: str
    note: str


@dataclasses.dataclass
class InstalledSkill:
    name: str
    description: str
    path: str


@dataclasses.dataclass
class CandidateReport:
    source: str
    root: str
    path: str
    name: str
    description: str
    sha256: str
    files: int
    bytes_total: int
    file_findings: list[FileFinding]
    risk_matches: list[RiskMatch]
    duplicate_matches: list[dict[str, object]]
    decision: str
    rationale: list[str]
    decision_record: dict[str, object]
    install_plan: dict[str, object]
    router_suggestion: dict[str, object]


RISK_RULES = [
    RiskRule(
        "prompt_override",
        "block",
        re.compile(
            r"\b(ignore|bypass|override|forget|disregard)\b.{0,80}\b(system|developer|higher[- ]priority|previous|prior|above)\b.{0,40}\b(instruction|message|rule|policy)s?\b",
            re.I,
        ),
        "Attempts to override higher-priority instructions.",
    ),
    RiskRule(
        "secrecy",
        "block",
        re.compile(r"\b(do not tell|hide this|without (telling|informing)|secretly|silently)\b", re.I),
        "Asks the agent to hide behavior from the user.",
    ),
    RiskRule(
        "secret_exfiltration",
        "block",
        re.compile(
            r"\b(upload|send|post|exfiltrate|leak|copy)\b.{0,80}\b(secret|token|api[_-]?key|ssh|credential|cookie|env|\.env|keychain)\b",
            re.I,
        ),
        "May exfiltrate credentials or private data.",
    ),
    RiskRule(
        "private_path",
        "warn",
        re.compile(r"(/Users/[^/\s]+|/home/[^/\s]+|~/(?:\.ssh|\.aws|\.config|Library/Keychains)|/etc/passwd)", re.I),
        "References private or machine-specific paths.",
    ),
    RiskRule(
        "remote_shell",
        "block",
        re.compile(r"\b(curl|wget)\b[^\n|;&]{0,120}(\|\s*(sh|bash|zsh)|sh\s*-c|bash\s*-c)", re.I),
        "Pipes remote content into a shell.",
    ),
    RiskRule(
        "destructive_shell",
        "block",
        re.compile(r"\b(rm\s+-rf\s+(/|~|\$HOME|\*)|mkfs\.[a-z0-9]+|diskutil\s+erase|dd\s+if=.*\s+of=/dev/)", re.I),
        "Contains destructive shell command patterns.",
    ),
    RiskRule(
        "persistence",
        "block",
        re.compile(
            r"\b(crontab|launchctl|systemctl\s+enable|schtasks|login\s+item|LaunchAgents|LaunchDaemons|\.bashrc|\.zshrc|shell\s+startup)\b",
            re.I,
        ),
        "May install persistence or change startup behavior.",
    ),
    RiskRule(
        "package_manager",
        "warn",
        re.compile(r"\b(npx\s+--yes|npm\s+install|pnpm\s+add|yarn\s+add|pip\s+install|uvx|curl\s+-fsSL|brew\s+install)\b", re.I),
        "Runs package managers or remote code paths.",
    ),
    RiskRule(
        "network_upload",
        "warn",
        re.compile(r"(\bcurl\b|fetch\s*\(|requests\.post\s*\(|urllib\.request|httpx\.post\s*\(|axios\.post\s*\()", re.I),
        "Contains network client/upload-capable code.",
    ),
    RiskRule(
        "svg_html_script",
        "warn",
        re.compile(r"(<script\b|onload=|onerror=|javascript:)", re.I),
        "SVG/HTML script or event handler found.",
    ),
]


STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "be",
    "by",
    "for",
    "from",
    "in",
    "into",
    "is",
    "it",
    "of",
    "on",
    "or",
    "the",
    "to",
    "use",
    "used",
    "using",
    "when",
    "with",
    "skill",
    "skills",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Static intake scanner for Codex skills.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--repo", help="GitHub repo as owner/name.")
    source.add_argument("--url", help="GitHub tree/blob URL pointing at a repo or skill path.")
    source.add_argument("--local", help="Local repository or skill directory.")
    parser.add_argument("--ref", default="main", help="Git ref for --repo. Default: main.")
    parser.add_argument("--path", action="append", default=[], help="Skill path inside the repo. Can be repeated.")
    parser.add_argument("--out", help="Write Markdown report to this path.")
    parser.add_argument("--json-out", help="Write JSON report to this path.")
    parser.add_argument("--router-out", help="Write only router patch suggestions to this path.")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of Markdown.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    temp_root: Path | None = None

    try:
        source_label, root, repo, ref, paths, temp_root = resolve_source(args)
        installed = load_installed_skills()
        reports = scan_candidates(source_label, root, paths, installed, repo, ref)
        payload = {
            "source": source_label,
            "repo": repo,
            "ref": ref,
            "candidate_count": len(reports),
            "reports": [candidate_to_dict(report) for report in reports],
        }

        markdown = render_markdown(payload, reports)

        if args.out:
            write_text(Path(args.out), markdown)
        if args.json_out:
            write_text(Path(args.json_out), json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
        if args.router_out:
            write_text(Path(args.router_out), render_router_patch(payload, reports))

        if args.json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            print(markdown)
    except IntakeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    finally:
        if temp_root is not None:
            shutil.rmtree(temp_root, ignore_errors=True)

    return 0


class IntakeError(RuntimeError):
    pass


def resolve_source(args: argparse.Namespace) -> tuple[str, Path, str | None, str | None, list[str], Path | None]:
    if args.local:
        root = Path(args.local).expanduser().resolve()
        if not root.exists():
            raise IntakeError(f"local path does not exist: {root}")
        return str(root), root, None, None, args.path, None

    repo = args.repo
    ref = args.ref
    paths = list(args.path)

    if args.url:
        repo, parsed_ref, parsed_path = parse_github_url(args.url)
        ref = parsed_ref or ref
        if parsed_path and not paths:
            paths = [parsed_path]

    if not repo or "/" not in repo:
        raise IntakeError("expected --repo owner/name or a GitHub URL")

    root, temp_root = download_github_zip(repo, ref)
    return f"https://github.com/{repo}/tree/{ref}", root, repo, ref, paths, temp_root


def parse_github_url(url: str) -> tuple[str, str | None, str | None]:
    parsed = urllib.parse.urlparse(url)
    if parsed.netloc.lower() != "github.com":
        raise IntakeError("only github.com URLs are supported")
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 2:
        raise IntakeError("GitHub URL must include owner/repo")
    owner, repo = parts[0], parts[1]
    if repo.endswith(".git"):
        repo = repo[:-4]
    ref = None
    subpath = None
    if len(parts) >= 5 and parts[2] in {"tree", "blob"}:
        ref = parts[3]
        subpath = "/".join(parts[4:])
    return f"{owner}/{repo}", ref, subpath


def download_github_zip(repo: str, ref: str) -> tuple[Path, Path]:
    temp = Path(tempfile.mkdtemp(prefix="skill-intake-"))
    zip_path = temp / "repo.zip"
    owner, name = repo.split("/", 1)
    quoted_ref = urllib.parse.quote(ref, safe="")
    url = f"https://codeload.github.com/{owner}/{name}/zip/{quoted_ref}"
    try:
        urllib.request.urlretrieve(url, zip_path)
    except Exception as exc:  # pragma: no cover - depends on network
        shutil.rmtree(temp, ignore_errors=True)
        raise IntakeError(f"failed to download {url}: {exc}") from exc

    extract_root = temp / "repo"
    extract_root.mkdir()
    safe_extract_zip(zip_path, extract_root)
    children = [child for child in extract_root.iterdir() if child.is_dir()]
    if len(children) == 1:
        return children[0], temp
    return extract_root, temp


def safe_extract_zip(zip_path: Path, dest: Path) -> None:
    dest_resolved = dest.resolve()
    with zipfile.ZipFile(zip_path) as archive:
        for member in archive.infolist():
            target = (dest / member.filename).resolve()
            if not str(target).startswith(str(dest_resolved) + os.sep) and target != dest_resolved:
                raise IntakeError(f"unsafe zip path: {member.filename}")
            mode = member.external_attr >> 16
            if stat.S_ISLNK(mode):
                raise IntakeError(f"zip contains symlink: {member.filename}")
        archive.extractall(dest)


def scan_candidates(
    source_label: str,
    root: Path,
    paths: list[str],
    installed: list[InstalledSkill],
    repo: str | None,
    ref: str | None,
) -> list[CandidateReport]:
    skill_dirs = find_candidate_dirs(root, paths)
    if not skill_dirs:
        raise IntakeError("no SKILL.md files found for the requested source/path")

    return [scan_skill(source_label, root, skill_dir, installed, repo, ref) for skill_dir in skill_dirs]


def find_candidate_dirs(root: Path, paths: list[str]) -> list[Path]:
    if paths:
        dirs: list[Path] = []
        for raw in paths:
            candidate = (root / raw).resolve()
            if not str(candidate).startswith(str(root.resolve())):
                raise IntakeError(f"path escapes repo root: {raw}")
            if candidate.is_file() and candidate.name == "SKILL.md":
                candidate = candidate.parent
            skill_md = candidate / "SKILL.md"
            if not skill_md.exists():
                raise IntakeError(f"SKILL.md not found under path: {raw}")
            dirs.append(candidate)
        return sorted(set(dirs))

    if (root / "SKILL.md").exists():
        return [root]

    dirs = []
    for skill_md in root.rglob("SKILL.md"):
        if should_skip(skill_md):
            continue
        dirs.append(skill_md.parent)
    return sorted(dirs)


def should_skip(path: Path) -> bool:
    return any(part in IGNORE_DIRS for part in path.parts)


def scan_skill(
    source_label: str,
    root: Path,
    skill_dir: Path,
    installed: list[InstalledSkill],
    repo: str | None,
    ref: str | None,
) -> CandidateReport:
    skill_md = skill_dir / "SKILL.md"
    skill_text = read_text_lossy(skill_md)
    frontmatter = parse_frontmatter(skill_text)
    name = frontmatter.get("name", skill_dir.name).strip() or skill_dir.name
    description = frontmatter.get("description", "").strip()
    sha256 = hashlib.sha256(skill_md.read_bytes()).hexdigest()

    files, bytes_total, file_findings = inventory_files(skill_dir)
    risk_matches = scan_risks(skill_dir)
    duplicate_matches = compare_installed(name, description, installed)
    decision, rationale = decide(frontmatter, file_findings, risk_matches, duplicate_matches)

    try:
        rel_path = str(skill_dir.resolve().relative_to(root.resolve()))
    except ValueError:
        rel_path = str(skill_dir)

    decision_record = build_decision_record(decision, rationale, file_findings, risk_matches, duplicate_matches)
    install_plan = build_install_plan(repo, ref, rel_path, name, decision)
    router_suggestion = build_router_suggestion(name, description, decision, duplicate_matches)

    return CandidateReport(
        source=source_label,
        root=str(root),
        path=rel_path,
        name=name,
        description=description,
        sha256=sha256,
        files=files,
        bytes_total=bytes_total,
        file_findings=file_findings,
        risk_matches=risk_matches,
        duplicate_matches=duplicate_matches,
        decision=decision,
        rationale=rationale,
        decision_record=decision_record,
        install_plan=install_plan,
        router_suggestion=router_suggestion,
    )


def parse_frontmatter(text: str) -> dict[str, str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    data: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip().strip("\"'")
        if key:
            data[key] = value
    return data


def inventory_files(skill_dir: Path) -> tuple[int, int, list[FileFinding]]:
    count = 0
    bytes_total = 0
    findings: list[FileFinding] = []
    for path in iter_files(skill_dir):
        rel = str(path.relative_to(skill_dir))
        count += 1
        try:
            stat_result = path.lstat()
        except OSError:
            continue
        bytes_total += stat_result.st_size

        if path.is_symlink():
            findings.append(FileFinding("symlink", "block", rel, "Symlink inside skill directory."))
        if any(part.startswith(".") for part in Path(rel).parts):
            findings.append(FileFinding("hidden_file", "warn", rel, "Hidden file inside skill directory."))
        if stat_result.st_mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH):
            findings.append(FileFinding("executable", "warn", rel, "Executable permission bit is set."))
        if stat_result.st_size > VERY_LARGE_FILE_BYTES:
            findings.append(FileFinding("very_large_file", "warn", rel, "Very large file may hide unreviewed content."))
        elif stat_result.st_size > LARGE_FILE_BYTES:
            findings.append(FileFinding("large_file", "info", rel, "Large file should be reviewed before trust."))

    return count, bytes_total, findings


def iter_files(root: Path) -> Iterable[Path]:
    for current, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        current_path = Path(current)
        for name in files:
            yield current_path / name


def scan_risks(skill_dir: Path) -> list[RiskMatch]:
    matches: list[RiskMatch] = []
    for path in iter_files(skill_dir):
        rel = str(path.relative_to(skill_dir))
        if not looks_textual(path):
            continue
        text = read_text_lossy(path, MAX_TEXT_BYTES)
        for line_no, line in enumerate(text.splitlines(), start=1):
            if is_defensive_context(rel, text, line_no, line):
                continue
            for rule in RISK_RULES:
                if rule.pattern.search(line):
                    matches.append(
                        RiskMatch(
                            category=rule.category,
                            severity=rule.severity,
                            path=rel,
                            line=line_no,
                            text=line.strip()[:220],
                            note=rule.note,
                        )
                    )
    return matches


def is_defensive_context(rel_path: str, text: str, line_no: int, line: str) -> bool:
    """Avoid flagging safety guidance as if it were malicious instruction."""
    if rel_path != "scripts/intake_github_skill.py":
        if "Block skills that tell Codex" in line:
            return True
        if "Treat `npx`, `npm install`, `pip install`, `uvx`, and `curl | sh`" in line:
            return True
        if "Reject or quarantine. Do not route to this skill." in line:
            return True
        return False

    lines = text.splitlines()
    if 0 < line_no <= len(lines):
        window_start = max(0, line_no - 8)
        window_end = min(len(lines), line_no + 4)
        window = "\n".join(lines[window_start:window_end])
        if "RiskRule(" in window or "RISK_RULES" in window:
            return True

    defensive_markers = (
        "RiskRule(",
        "re.compile(",
        "import urllib.request",
        "urllib.request.urlretrieve",
        "Treat `npx`, `npm install`, `pip install`, `uvx`, and `curl | sh`",
        "prompt_override",
        "secret_exfiltration",
        "remote_shell",
        "destructive_shell",
        "persistence",
        "package_manager",
        "svg_html_script",
        "Attempts to override higher-priority instructions.",
        "Pipes remote content into a shell.",
        "Contains destructive shell command patterns.",
    )
    return any(marker in line for marker in defensive_markers)


def looks_textual(path: Path) -> bool:
    if path.name == "SKILL.md":
        return True
    if path.suffix.lower() in TEXT_EXTS:
        return True
    try:
        chunk = path.read_bytes()[:2048]
    except OSError:
        return False
    if b"\0" in chunk:
        return False
    try:
        chunk.decode("utf-8")
        return True
    except UnicodeDecodeError:
        return False


def read_text_lossy(path: Path, limit: int | None = None) -> str:
    data = path.read_bytes()
    if limit is not None:
        data = data[:limit]
    return data.decode("utf-8", errors="replace")


def load_installed_skills() -> list[InstalledSkill]:
    roots = default_skill_roots()
    seen: set[Path] = set()
    installed: list[InstalledSkill] = []
    for root in roots:
        if not root.exists():
            continue
        for skill_md in root.rglob("SKILL.md"):
            if should_skip(skill_md):
                continue
            parent = skill_md.parent.resolve()
            if parent in seen:
                continue
            seen.add(parent)
            text = read_text_lossy(skill_md, MAX_TEXT_BYTES)
            frontmatter = parse_frontmatter(text)
            name = frontmatter.get("name", parent.name).strip() or parent.name
            description = frontmatter.get("description", "").strip()
            installed.append(InstalledSkill(name=name, description=description, path=str(parent)))
    return installed


def default_skill_roots() -> list[Path]:
    home = Path.home()
    codex_home = Path(os.environ.get("CODEX_HOME", home / ".codex")).expanduser()
    return [
        codex_home / "skills",
        home / ".agents" / "skills",
        codex_home / "skills" / ".system",
        codex_home / "plugins" / "cache",
    ]


def compare_installed(name: str, description: str, installed: list[InstalledSkill]) -> list[dict[str, object]]:
    candidate_words = word_set(f"{name} {description}")
    matches: list[dict[str, object]] = []
    for item in installed:
        if item.name == name:
            matches.append(
                {
                    "kind": "same-name",
                    "score": 1.0,
                    "name": item.name,
                    "description": item.description,
                    "path": item.path,
                }
            )
            continue
        item_words = word_set(f"{item.name} {item.description}")
        score = overlap_score(candidate_words, item_words)
        if score >= 0.55 and len(candidate_words) >= 4 and len(item_words) >= 4:
            matches.append(
                {
                    "kind": "similar-description",
                    "score": round(score, 3),
                    "name": item.name,
                    "description": item.description,
                    "path": item.path,
                }
            )
    matches.sort(key=lambda item: float(item["score"]), reverse=True)
    return matches[:8]


def word_set(text: str) -> set[str]:
    words = set(re.findall(r"[a-zA-Z0-9][a-zA-Z0-9_-]{2,}", text.lower()))
    return {word for word in words if word not in STOP_WORDS}


def overlap_score(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / min(len(left), len(right))


def decide(
    frontmatter: dict[str, str],
    file_findings: list[FileFinding],
    risk_matches: list[RiskMatch],
    duplicate_matches: list[dict[str, object]],
) -> tuple[str, list[str]]:
    rationale: list[str] = []
    block_count = sum(1 for item in risk_matches if item.severity == "block")
    block_count += sum(1 for item in file_findings if item.severity == "block")
    warn_count = sum(1 for item in risk_matches if item.severity == "warn")
    warn_count += sum(1 for item in file_findings if item.severity == "warn")

    if block_count:
        rationale.append(f"{block_count} blocking safety finding(s).")
        return "reject", rationale

    if not frontmatter.get("name") or not frontmatter.get("description"):
        rationale.append("Missing frontmatter name or description.")
        return "manual-review", rationale

    same_name = [item for item in duplicate_matches if item["kind"] == "same-name"]
    if same_name:
        rationale.append("Same-name installed skill found; compare before installing.")
        return "defer-duplicate", rationale

    strong_overlap = [
        item
        for item in duplicate_matches
        if item["kind"] == "similar-description" and float(item["score"]) >= 0.75
    ]
    if strong_overlap:
        rationale.append("Strong overlap with installed skill descriptions.")
        return "defer-duplicate", rationale

    if warn_count:
        rationale.append(f"{warn_count} warning finding(s) need review.")
        return "manual-review", rationale

    if duplicate_matches:
        rationale.append("Some overlap with installed skills; route narrowly if installed.")
        return "explicit-only", rationale

    rationale.append("No obvious blocker found and no strong installed duplicate detected.")
    return "install-candidate", rationale


def build_decision_record(
    decision: str,
    rationale: list[str],
    file_findings: list[FileFinding],
    risk_matches: list[RiskMatch],
    duplicate_matches: list[dict[str, object]],
) -> dict[str, object]:
    blocking = [item for item in file_findings if item.severity == "block"]
    blocking.extend(item for item in risk_matches if item.severity == "block")
    warnings = [item for item in file_findings if item.severity == "warn"]
    warnings.extend(item for item in risk_matches if item.severity == "warn")
    same_name = [item for item in duplicate_matches if item["kind"] == "same-name"]
    similar = [item for item in duplicate_matches if item["kind"] == "similar-description"]
    return {
        "decision": decision,
        "rationale": rationale,
        "counts": {
            "blocking_findings": len(blocking),
            "warning_findings": len(warnings),
            "duplicate_matches": len(duplicate_matches),
            "same_name_matches": len(same_name),
            "similar_description_matches": len(similar),
        },
        "requires_user_approval": decision in {"install-candidate", "manual-review", "explicit-only"},
        "safe_to_route_by_default": decision == "install-candidate",
    }


def build_install_plan(
    repo: str | None,
    ref: str | None,
    path: str,
    name: str,
    decision: str,
) -> dict[str, object]:
    eligible = decision in {"install-candidate", "manual-review", "explicit-only"}
    if not repo:
        return {
            "eligible": False,
            "reason": "No GitHub repo source was provided; install manually only after review.",
            "command": None,
        }
    if not eligible:
        return {
            "eligible": False,
            "reason": f"Decision `{decision}` should not be installed by default.",
            "command": None,
        }

    command_parts = [
        "python3",
        "~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py",
        "--repo",
        shlex.quote(repo),
        "--ref",
        shlex.quote(ref or "main"),
        "--path",
        shlex.quote(path),
    ]
    if path in {"", "."}:
        command_parts.extend(["--name", shlex.quote(name)])
    return {
        "eligible": True,
        "reason": "Run only after user approval and after reviewing the report.",
        "skill_name_after_install": name if path in {"", "."} else Path(path).name,
        "command": " ".join(command_parts),
    }


def build_router_suggestion(
    name: str,
    description: str,
    decision: str,
    duplicate_matches: list[dict[str, object]],
) -> dict[str, object]:
    trigger = infer_trigger(name, description)
    entry = f"- {trigger} -> `{name}`"
    duplicate_names = [str(item["name"]) for item in duplicate_matches[:3]]

    if decision == "install-candidate":
        section = "Default Winners or the most specific matching domain section"
        note = "Candidate can become a default route if the human review agrees it is the strongest skill for this trigger."
        patch = entry
    elif decision in {"manual-review", "explicit-only"}:
        section = "Explicit-Only or the matching domain section"
        note = "Route narrowly only when the exact platform/tool/workflow is named."
        patch = f"- Explicit {trigger} -> `{name}`"
    elif decision == "defer-duplicate":
        section = "Demoted or Duplicate Skills"
        note = "Keep existing stronger/default skill routes; do not install or route by default unless a clear advantage is found."
        covered_by = ", ".join(f"`{item}`" for item in duplicate_names) or "an installed skill"
        patch = f"- `{name}` is covered by {covered_by}; do not route by default."
    else:
        section = "Rejected or Quarantined Skills"
        note = "Do not install or route. Keep only a private audit note if needed."
        patch = f"- `{name}` rejected during intake; do not install or route."

    return {
        "section": section,
        "entry": entry,
        "patch": patch,
        "note": note,
        "overlaps": duplicate_names,
    }


def infer_trigger(name: str, description: str) -> str:
    words = [word for word in re.split(r"[-_\s]+", name) if word]
    if words:
        label = " ".join(words[:4])
    else:
        description_words = re.findall(r"[A-Za-z0-9][A-Za-z0-9_-]{2,}", description)
        label = " ".join(description_words[:4]) if description_words else "Specific reviewed workflow"
    return f"{label} workflow"


def candidate_to_dict(report: CandidateReport) -> dict[str, object]:
    return {
        "source": report.source,
        "root": report.root,
        "path": report.path,
        "name": report.name,
        "description": report.description,
        "sha256": report.sha256,
        "files": report.files,
        "bytes_total": report.bytes_total,
        "file_findings": [dataclasses.asdict(item) for item in report.file_findings],
        "risk_matches": [dataclasses.asdict(item) for item in report.risk_matches],
        "duplicate_matches": report.duplicate_matches,
        "decision": report.decision,
        "rationale": report.rationale,
        "decision_record": report.decision_record,
        "install_plan": report.install_plan,
        "router_suggestion": report.router_suggestion,
    }


def render_markdown(payload: dict[str, object], reports: list[CandidateReport]) -> str:
    lines: list[str] = []
    lines.append("# Skill Intake Report")
    lines.append("")
    lines.append(f"- Source: `{payload['source']}`")
    if payload.get("repo"):
        lines.append(f"- Repo: `{payload['repo']}`")
    if payload.get("ref"):
        lines.append(f"- Ref: `{payload['ref']}`")
    lines.append(f"- Candidates: `{len(reports)}`")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("| Skill | Path | Decision | Files | Findings |")
    lines.append("|---|---|---:|---:|---:|")
    for report in reports:
        findings = len(report.file_findings) + len(report.risk_matches)
        lines.append(
            f"| `{escape_table(report.name)}` | `{escape_table(report.path)}` | `{report.decision}` | {report.files} | {findings} |"
        )
    lines.append("")

    for report in reports:
        lines.extend(render_report_detail(report))
    lines.append("## Router Patch Suggestions")
    lines.append("")
    lines.extend(render_router_patch_lines(reports))
    return "\n".join(lines).rstrip() + "\n"


def render_report_detail(report: CandidateReport) -> list[str]:
    lines: list[str] = []
    lines.append(f"## `{report.name}`")
    lines.append("")
    lines.append(f"- Path: `{report.path}`")
    lines.append(f"- Description: {report.description or '(missing)'}")
    lines.append(f"- SHA-256 of SKILL.md: `{report.sha256}`")
    lines.append(f"- Size: {report.files} file(s), {report.bytes_total} byte(s)")
    lines.append(f"- Decision: `{report.decision}`")
    lines.append("- Rationale:")
    for item in report.rationale:
        lines.append(f"  - {item}")
    lines.append("")

    if report.file_findings:
        lines.append("### File Findings")
        lines.append("")
        lines.append("| Severity | Category | Path | Note |")
        lines.append("|---|---|---|---|")
        for item in report.file_findings[:20]:
            lines.append(f"| {item.severity} | {item.category} | `{escape_table(item.path)}` | {escape_table(item.note)} |")
        if len(report.file_findings) > 20:
            lines.append(f"| info | truncated | | {len(report.file_findings) - 20} more finding(s) omitted |")
        lines.append("")

    if report.risk_matches:
        lines.append("### Risk Matches")
        lines.append("")
        lines.append("| Severity | Category | Location | Text |")
        lines.append("|---|---|---|---|")
        for item in report.risk_matches[:30]:
            location = f"{item.path}:{item.line}"
            lines.append(
                f"| {item.severity} | {item.category} | `{escape_table(location)}` | {escape_table(item.text)} |"
            )
        if len(report.risk_matches) > 30:
            lines.append(f"| info | truncated | | {len(report.risk_matches) - 30} more match(es) omitted |")
        lines.append("")

    if report.duplicate_matches:
        lines.append("### Installed Skill Overlap")
        lines.append("")
        lines.append("| Kind | Score | Installed Skill | Description |")
        lines.append("|---|---:|---|---|")
        for item in report.duplicate_matches:
            lines.append(
                f"| {item['kind']} | {item['score']} | `{escape_table(str(item['name']))}` | {escape_table(str(item['description'])[:180])} |"
            )
        lines.append("")

    lines.append("### Suggested Next Step")
    lines.append("")
    lines.extend(suggest_next_step(report))
    lines.append("")
    lines.append("### Install Plan")
    lines.append("")
    install_plan = report.install_plan
    lines.append(f"- Eligible: `{str(install_plan['eligible']).lower()}`")
    lines.append(f"- Reason: {install_plan['reason']}")
    if install_plan.get("command"):
        lines.append("")
        lines.append("```bash")
        lines.append(str(install_plan["command"]))
        lines.append("```")
    lines.append("")
    lines.append("### Router Suggestion")
    lines.append("")
    router = report.router_suggestion
    lines.append(f"- Section: `{router['section']}`")
    lines.append(f"- Note: {router['note']}")
    lines.append("")
    lines.append("```markdown")
    lines.append(str(router["patch"]))
    lines.append("```")
    lines.append("")
    return lines


def suggest_next_step(report: CandidateReport) -> list[str]:
    if report.decision == "install-candidate":
        return [
            "Ask the user for approval, install with the generated command, then add the router rule after confirming the installed skill name."
        ]
    if report.decision == "manual-review":
        return [
            "Review the warnings and any helper files manually. If accepted, install only after user approval and route narrowly."
        ]
    if report.decision == "explicit-only":
        return [
            "Install only if the exact platform/tool is wanted. Route it as explicit-only, not as a default winner."
        ]
    if report.decision == "defer-duplicate":
        return [
            "Do not install by default. Keep the existing stronger skill as the route unless this candidate proves a clear advantage."
        ]
    return ["Reject or quarantine. Do not route to this skill."]


def render_router_patch(payload: dict[str, object], reports: list[CandidateReport]) -> str:
    lines: list[str] = []
    lines.append("# Router Patch Suggestions")
    lines.append("")
    lines.append(f"- Source: `{payload['source']}`")
    if payload.get("repo"):
        lines.append(f"- Repo: `{payload['repo']}`")
    if payload.get("ref"):
        lines.append(f"- Ref: `{payload['ref']}`")
    lines.append("")
    lines.extend(render_router_patch_lines(reports))
    return "\n".join(lines).rstrip() + "\n"


def render_router_patch_lines(reports: list[CandidateReport]) -> list[str]:
    lines: list[str] = []
    for report in reports:
        router = report.router_suggestion
        lines.append(f"### `{report.name}`")
        lines.append("")
        lines.append(f"- Decision: `{report.decision}`")
        lines.append(f"- Section: `{router['section']}`")
        lines.append(f"- Note: {router['note']}")
        if router.get("overlaps"):
            overlaps = ", ".join(f"`{name}`" for name in router["overlaps"])
            lines.append(f"- Overlaps: {overlaps}")
        lines.append("")
        lines.append("```markdown")
        lines.append(str(router["patch"]))
        lines.append("```")
        lines.append("")
    return lines


def escape_table(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
