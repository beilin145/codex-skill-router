#!/usr/bin/env python3
"""Run the standard skill intake workflow end to end."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path


class WorkflowError(RuntimeError):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run scan -> report -> registry -> router workflow.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--repo", help="GitHub repo as owner/name.")
    source.add_argument("--url", help="GitHub tree/blob URL pointing at a repo or skill path.")
    source.add_argument("--local", help="Local repository or skill directory.")
    parser.add_argument("--ref", default="main", help="Git ref for --repo. Default: main.")
    parser.add_argument("--path", action="append", default=[], help="Skill path inside the repo. Can repeat.")
    parser.add_argument("--work-dir", help="Directory for generated reports. Defaults to a temp directory.")
    parser.add_argument("--router", help="Router SKILL.md path.")
    parser.add_argument("--registry", help="Registry JSON path.")
    parser.add_argument("--candidate", action="append", default=[], help="Candidate skill name to apply/record. Can repeat.")
    parser.add_argument("--apply-router", action="store_true", help="Apply accepted decisions to the router managed section.")
    parser.add_argument("--record-registry", action="store_true", help="Record selected decisions in the registry.")
    parser.add_argument("--install-approved", action="store_true", help="Install install-candidate decisions with generated commands.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        work_dir = Path(args.work_dir).expanduser() if args.work_dir else Path(tempfile.mkdtemp(prefix="skill-intake-workflow-"))
        work_dir.mkdir(parents=True, exist_ok=True)
        intake_json = work_dir / "intake.json"
        intake_md = work_dir / "intake.md"
        router_md = work_dir / "router.md"

        run_intake(args, intake_json, intake_md, router_md)
        if args.record_registry:
            run_registry(args, intake_json)
        if args.apply_router:
            run_apply(args, intake_json)
        if args.install_approved:
            run_install(intake_json)

        print(f"intake report: {intake_md}")
        print(f"intake json: {intake_json}")
        print(f"router suggestions: {router_md}")
    except WorkflowError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


def script_path(name: str) -> str:
    return str(Path(__file__).with_name(name))


def run(command: list[str]) -> str:
    result = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        raise WorkflowError(result.stderr.strip() or result.stdout.strip() or f"command failed: {command[0]}")
    return result.stdout


def run_intake(args: argparse.Namespace, intake_json: Path, intake_md: Path, router_md: Path) -> None:
    command = [sys.executable, script_path("intake_github_skill.py")]
    if args.repo:
        command.extend(["--repo", args.repo, "--ref", args.ref])
    elif args.url:
        command.extend(["--url", args.url])
    else:
        command.extend(["--local", args.local])
    for path in args.path:
        command.extend(["--path", path])
    command.extend(["--out", str(intake_md), "--json-out", str(intake_json), "--router-out", str(router_md)])
    run(command)


def run_registry(args: argparse.Namespace, intake_json: Path) -> None:
    command = [sys.executable, script_path("skill_registry.py")]
    if args.registry:
        command.extend(["--registry", args.registry])
    command.extend(["record", "--intake-json", str(intake_json)])
    for candidate in args.candidate:
        command.extend(["--candidate", candidate])
    print(run(command).strip())


def run_apply(args: argparse.Namespace, intake_json: Path) -> None:
    command = [sys.executable, script_path("apply_intake_decision.py"), "--intake-json", str(intake_json), "--apply"]
    if args.router:
        command.extend(["--router", args.router])
    if args.registry and not args.record_registry:
        command.extend(["--registry", args.registry])
    for candidate in args.candidate:
        command.extend(["--candidate", candidate])
    print(run(command).strip())


def run_install(intake_json: Path) -> None:
    import json

    data = json.loads(intake_json.read_text(encoding="utf-8"))
    reports = data.get("reports") if isinstance(data.get("reports"), list) else []
    for report in reports:
        if not isinstance(report, dict) or report.get("decision") != "install-candidate":
            continue
        install_plan = report.get("install_plan") if isinstance(report.get("install_plan"), dict) else {}
        command = install_plan.get("command")
        if not command:
            continue
        run(["sh", "-c", str(command)])


if __name__ == "__main__":
    raise SystemExit(main())
