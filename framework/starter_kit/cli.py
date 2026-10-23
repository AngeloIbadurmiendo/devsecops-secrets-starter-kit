from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import ConfigurationError, ProjectConfig, read_config, write_config
from .doctor import doctor_report
from .generator import GenerationConflictError, generate_project
from .lifecycle import (
    LifecycleError,
    apply_environment,
    destroy_environment,
    verify_environment,
    write_lifecycle_result,
)
from .planner import PlanError, build_plan, write_plan


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="feria-starter",
        description="Generate the validated DevSecOps baseline without changing Azure.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor = subparsers.add_parser("doctor", help="Inspect local prerequisites.")
    doctor.add_argument("--mode", choices=("local", "cloud"), default="local")
    doctor.add_argument("--json", action="store_true", dest="as_json")

    init = subparsers.add_parser("init", help="Create a declarative project file.")
    init.add_argument("--name")
    init.add_argument("--environment", choices=("dev", "test"), default="dev")
    init.add_argument(
        "--expires-on",
        default="pending",
        help="Planned deletion date (YYYY-MM-DD); required before plan.",
    )
    init.add_argument(
        "--sops-age-recipient",
        action="append",
        default=[],
        help="Public age1 recipient; repeat for each authorized identity.",
    )
    init.add_argument("--output", type=Path, default=Path("feria-project.json"))
    init.add_argument("--non-interactive", action="store_true")

    generate = subparsers.add_parser(
        "generate", help="Generate the local security baseline."
    )
    generate.add_argument("--config", type=Path, default=Path("feria-project.json"))
    generate.add_argument("--output", type=Path, required=True)

    plan = subparsers.add_parser(
        "plan", help="Compile Bicep and optionally run Azure ARM what-if."
    )
    plan.add_argument("--config", type=Path, default=Path("feria-project.json"))
    plan.add_argument("--template", type=Path)
    plan.add_argument("--output", type=Path, default=Path(".feria/plan.json"))
    plan.add_argument(
        "--what-if",
        action="store_true",
        help="Query Azure Resource Manager without applying the deployment.",
    )
    plan.add_argument(
        "--resource-group",
        help="Existing tagged target group; required with --what-if.",
    )

    apply = subparsers.add_parser(
        "apply", help="Deploy the validated profile into an existing tagged group."
    )
    apply.add_argument("--config", type=Path, default=Path("feria-project.json"))
    apply.add_argument("--template", type=Path)
    apply.add_argument("--resource-group", required=True)
    apply.add_argument("--confirm", required=True)
    apply.add_argument("--output", type=Path, default=Path(".feria/apply.json"))

    verify = subparsers.add_parser(
        "verify", help="Verify the deployed profile without retaining identifiers."
    )
    verify.add_argument("--config", type=Path, default=Path("feria-project.json"))
    verify.add_argument("--resource-group", required=True)
    verify.add_argument("--output", type=Path, default=Path(".feria/verify.json"))

    destroy = subparsers.add_parser(
        "destroy", help="Delete an exactly matched tagged resource group."
    )
    destroy.add_argument("--config", type=Path, default=Path("feria-project.json"))
    destroy.add_argument("--resource-group", required=True)
    destroy.add_argument("--confirm", required=True)
    destroy.add_argument("--output", type=Path, default=Path(".feria/destroy.json"))
    return parser


def _run_doctor(args: argparse.Namespace) -> int:
    report = doctor_report(args.mode)
    if args.as_json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"Mode: {report['mode']}")
        for tool in report["tools"]:
            state = "ok" if tool["available"] else "missing"
            requirement = "required" if tool["required"] else "optional"
            print(f"- {tool['name']}: {state} ({requirement})")
        print("Ready" if report["ready"] else "Blocked")
    return 0 if report["ready"] else 2


def _run_init(args: argparse.Namespace) -> int:
    name = args.name
    if not name and args.non_interactive:
        raise ConfigurationError("--name is required with --non-interactive.")
    if not name:
        name = input("Project name (lowercase and hyphens): ").strip()
    config = ProjectConfig(
        project_name=name,
        environment=args.environment,
        expires_on=args.expires_on,
        sops_age_recipients=tuple(args.sops_age_recipient),
    )
    write_config(args.output, config)
    print(f"Created {args.output}")
    print("Selected preflight profile: functions-flex-python in brazilsouth.")
    if config.sops_age_recipients:
        print(f"Configured {len(config.sops_age_recipients)} public SOPS recipient(s).")
    else:
        print("SOPS recipients are pending; generate will omit .sops.yaml safely.")
    print("Deployment validation is still required; no Azure resources were changed.")
    return 0


def _run_generate(args: argparse.Namespace) -> int:
    config = read_config(args.config)
    manifest = generate_project(config, args.output)
    print(f"Generated {len(manifest['files'])} files in {args.output}")
    if ".sops.yaml" not in manifest["files"]:
        print("SOPS configuration omitted because no public recipients were supplied.")
    print("No remote resources were changed.")
    return 0


def _run_plan(args: argparse.Namespace) -> int:
    config = read_config(args.config)
    template = args.template or args.config.parent / "infra/bicep/main.bicep"
    plan = build_plan(
        config,
        template,
        run_what_if=args.what_if,
        resource_group=args.resource_group,
    )
    write_plan(args.output, plan)
    mode = "Azure what-if" if args.what_if else "local Bicep compilation"
    print(f"Plan created with {mode}: {args.output}")
    print("No Azure resources were changed.")
    return 0


def _run_apply(args: argparse.Namespace) -> int:
    config = read_config(args.config)
    template = args.template or args.config.parent / "infra/bicep/main.bicep"
    result = apply_environment(
        config, template, args.resource_group, args.confirm
    )
    write_lifecycle_result(args.output, result)
    print(f"Deployment completed; sanitized result: {args.output}")
    return 0


def _run_verify(args: argparse.Namespace) -> int:
    config = read_config(args.config)
    result = verify_environment(config, args.resource_group)
    write_lifecycle_result(args.output, result)
    print(f"Verification completed; sanitized result: {args.output}")
    print("No Azure resources were changed.")
    return 0


def _run_destroy(args: argparse.Namespace) -> int:
    config = read_config(args.config)
    result = destroy_environment(config, args.resource_group, args.confirm)
    write_lifecycle_result(args.output, result)
    print(f"Destruction completed; sanitized result: {args.output}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "doctor":
            return _run_doctor(args)
        if args.command == "init":
            return _run_init(args)
        if args.command == "generate":
            return _run_generate(args)
        if args.command == "plan":
            return _run_plan(args)
        if args.command == "apply":
            return _run_apply(args)
        if args.command == "verify":
            return _run_verify(args)
        if args.command == "destroy":
            return _run_destroy(args)
    except (
        ConfigurationError,
        FileExistsError,
        GenerationConflictError,
        LifecycleError,
        PlanError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    raise AssertionError(f"Unhandled command: {args.command}")
