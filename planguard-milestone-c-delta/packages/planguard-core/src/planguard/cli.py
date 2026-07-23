"""PlanGuard Milestone C command-line interface."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from planguard.analysis.load import load_analysis_bundle
from planguard.artifacts.codec import default_codec
from planguard.artifacts.models import BudgetPolicyArtifact, EvaluationStatus, ProducerIdentity
from planguard.canonical import canonical_json_text
from planguard.contracts.generate import generate_contracts
from planguard.errors import PlanGuardError
from planguard.policy.engine import evaluate_policy
from planguard.reporting.render import render_html, render_json, render_terminal
from planguard.store.bundle import export_run_bundle
from planguard.store.filesystem import FilesystemArtifactStore
from planguard.store.index import ArtifactIndex


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="planguard")
    subcommands = parser.add_subparsers(dest="command", required=True)

    validate = subcommands.add_parser("validate", help="Validate one artifact JSON file")
    validate.add_argument("path", type=Path)

    show = subcommands.add_parser("show", help="Show one artifact from a store")
    show.add_argument("artifact_id")
    show.add_argument("--store", type=Path, default=Path(".planguard"))

    inspect = subcommands.add_parser("inspect", help="Inspect a completed run")
    inspect.add_argument("run_id")
    inspect.add_argument("--store", type=Path, default=Path(".planguard"))
    inspect.add_argument("--format", choices=("terminal", "json"), default="terminal")

    analyze = subcommands.add_parser("analyze", help="Reanalyze query executions for a run")
    analyze.add_argument("run_id")
    analyze.add_argument("--store", type=Path, default=Path(".planguard"))
    analyze.add_argument("--persist", action="store_true")

    report = subcommands.add_parser("report", help="Render a completed run report")
    report.add_argument("run_id")
    report.add_argument("--store", type=Path, default=Path(".planguard"))
    report.add_argument("--format", choices=("terminal", "json", "html"), default="terminal")
    report.add_argument("--output", type=Path)

    policy = subcommands.add_parser("policy-evaluate", help="Evaluate a budget policy artifact")
    policy.add_argument("run_id")
    policy.add_argument("policy_path", type=Path)
    policy.add_argument("--store", type=Path, default=Path(".planguard"))
    policy.add_argument("--persist", action="store_true")

    list_command = subcommands.add_parser("list", help="List artifacts in a store")
    list_command.add_argument("--store", type=Path, default=Path(".planguard"))
    list_command.add_argument("--kind")

    verify = subcommands.add_parser("verify", help="Verify one store or artifact")
    verify.add_argument("--store", type=Path, default=Path(".planguard"))
    verify.add_argument("--artifact-id")

    index_rebuild = subcommands.add_parser("index-rebuild", help="Rebuild the disposable metadata index")
    index_rebuild.add_argument("--store", type=Path, default=Path(".planguard"))
    index_rebuild.add_argument("--index", type=Path)

    search = subcommands.add_parser("search", help="Search indexed artifacts")
    search.add_argument("query", nargs="?")
    search.add_argument("--store", type=Path, default=Path(".planguard"))
    search.add_argument("--index", type=Path)
    search.add_argument("--kind")
    search.add_argument("--run-id")
    search.add_argument("--motif")
    search.add_argument("--limit", type=int, default=50)

    export = subcommands.add_parser("export-run", help="Export one portable run bundle")
    export.add_argument("run_id")
    export.add_argument("--store", type=Path, default=Path(".planguard"))
    export.add_argument("--output", type=Path)

    schemas = subcommands.add_parser("generate-contracts", help="Regenerate contracts")
    schemas.add_argument("--schema-dir", type=Path, default=Path("schemas/generated"))
    schemas.add_argument(
        "--typescript",
        type=Path,
        default=Path("apps/workbench-ui/src/generated/artifact-types.ts"),
    )
    return parser


def _render(bundle, format: str):
    evaluation = bundle.budget_evaluations[-1] if bundle.budget_evaluations else None
    if format == "terminal":
        return render_terminal(bundle, evaluation=evaluation)
    if format == "json":
        return render_json(bundle, evaluation=evaluation)
    return render_html(bundle, evaluation=evaluation)


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "validate":
            artifact = default_codec.decode(args.path.read_bytes())
            print(
                json.dumps(
                    {
                        "valid": True,
                        "artifact_id": artifact.artifact_id,
                        "artifact_kind": artifact.artifact_kind,
                        "schema_version": artifact.schema_version,
                        "content_hash": artifact.content_hash,
                    },
                    indent=2,
                )
            )
            return 0

        if args.command == "show":
            artifact = FilesystemArtifactStore(args.store).load(args.artifact_id)
            print(canonical_json_text(artifact, pretty=True))
            return 0

        if args.command in {"inspect", "report"}:
            _, bundle = load_analysis_bundle(FilesystemArtifactStore(args.store), args.run_id)
            rendered = _render(bundle, args.format)
            output = getattr(args, "output", None)
            if output:
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(rendered, encoding="utf-8")
                print(output)
            else:
                print(rendered, end="" if rendered.endswith("\n") else "\n")
            return 0

        if args.command == "analyze":
            store = FilesystemArtifactStore(args.store)
            _, bundle = load_analysis_bundle(store, args.run_id, reanalyze_if_missing=True)
            if args.persist:
                for artifact in bundle.all_derived_artifacts():
                    store.save(artifact)
            print(render_terminal(bundle), end="")
            return 0

        if args.command == "policy-evaluate":
            store = FilesystemArtifactStore(args.store)
            _, bundle = load_analysis_bundle(store, args.run_id)
            policy_artifact = default_codec.decode(args.policy_path.read_bytes())
            if not isinstance(policy_artifact, BudgetPolicyArtifact):
                raise ValueError("policy_path must contain a budget_policy artifact")
            evaluation = evaluate_policy(
                bundle,
                policy_artifact,
                producer=ProducerIdentity(name="planguard", version="0.3.0", build="cli"),
            )
            if args.persist:
                store.save(evaluation)
            print(render_terminal(bundle, evaluation=evaluation), end="")
            return 2 if evaluation.payload.status == EvaluationStatus.FAILED else 0

        if args.command == "list":
            records = FilesystemArtifactStore(args.store).list(artifact_kind=args.kind)
            for record in records:
                print(
                    f"{record.artifact_id}\t{record.artifact_kind}\t"
                    f"{record.schema_version}\t{record.content_hash}"
                )
            return 0

        if args.command == "verify":
            store = FilesystemArtifactStore(args.store)
            if args.artifact_id:
                result = {args.artifact_id: store.verify(args.artifact_id)}
            else:
                result = store.verify_all()
            print(json.dumps(result, sort_keys=True, indent=2))
            return 0 if all(result.values()) else 2

        if args.command == "index-rebuild":
            store = FilesystemArtifactStore(args.store)
            index_path = args.index or (args.store / "registry.sqlite3")
            count = ArtifactIndex(index_path).rebuild(store)
            print(json.dumps({"status": "rebuilt", "artifact_count": count, "index": str(index_path)}, indent=2))
            return 0

        if args.command == "search":
            store = FilesystemArtifactStore(args.store)
            index_path = args.index or (args.store / "registry.sqlite3")
            index = ArtifactIndex(index_path)
            index.sync(store)
            page = index.search(query=args.query, artifact_kind=args.kind, run_id=args.run_id, motif_key=args.motif, limit=args.limit)
            print(json.dumps({"items": list(page.items), "total": page.total}, indent=2, default=str))
            return 0

        if args.command == "export-run":
            output = args.output or Path(f"{args.run_id}.planguard.zip")
            output.write_bytes(export_run_bundle(FilesystemArtifactStore(args.store), args.run_id))
            print(output)
            return 0

        if args.command == "generate-contracts":
            generate_contracts(args.schema_dir, args.typescript)
            print(f"Generated schemas in {args.schema_dir} and types in {args.typescript}")
            return 0
    except (PlanGuardError, OSError, ValueError, TypeError) as exc:
        if isinstance(exc, PlanGuardError):
            payload = {"error": exc.code, "message": exc.message, "details": exc.details}
        else:
            payload = {"error": type(exc).__name__, "message": str(exc)}
        print(json.dumps(payload, indent=2), file=sys.stderr)
        return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
