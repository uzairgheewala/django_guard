"""PlanGuard Milestone E command-line interface."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from planguard.analysis.load import load_analysis_bundle
from planguard.artifacts.codec import default_codec
from planguard.artifacts.models import BudgetPolicyArtifact, EvaluationStatus, ProducerIdentity, ScenarioInstanceArtifact, ObservedQueryFamilyArtifact, PlanObservationArtifact, ComparisonReportArtifact
from planguard.canonical import canonical_json_text
from planguard.contracts.generate import generate_contracts
from planguard.errors import PlanGuardError
from planguard.policy.engine import evaluate_policy
from planguard.lab.academic import build_academic_catalog
from planguard.scenario import ScenarioRunner, instantiate
from planguard.postgres import import_plan, analyze_plan
from planguard.comparison import compare_runs
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


    scenario_catalog = subcommands.add_parser("scenario-catalog", help="List generic templates, academic bindings, and mutations")
    scenario_catalog.add_argument("--store", type=Path, default=Path(".planguard"))

    scenario_instantiate = subcommands.add_parser("scenario-instantiate", help="Create one deterministic academic scenario instance")
    scenario_instantiate.add_argument("template_key")
    scenario_instantiate.add_argument("binding_key")
    scenario_instantiate.add_argument("--variant", choices=("naive", "optimized"), default="naive")
    scenario_instantiate.add_argument("--parameter", action="append", default=[], help="KEY=JSON_VALUE")
    scenario_instantiate.add_argument("--mutation", action="append", default=[], help="MUTATION_KEY")
    scenario_instantiate.add_argument("--seed", type=int, default=1)
    scenario_instantiate.add_argument("--store", type=Path, default=Path(".planguard"))

    scenario_run = subcommands.add_parser("scenario-run", help="Execute one persisted or inline academic scenario")
    scenario_run.add_argument("scenario_instance_id", nargs="?")
    scenario_run.add_argument("--template")
    scenario_run.add_argument("--binding")
    scenario_run.add_argument("--variant", choices=("naive", "optimized"), default="naive")
    scenario_run.add_argument("--parameter", action="append", default=[], help="KEY=JSON_VALUE")
    scenario_run.add_argument("--mutation", action="append", default=[], help="MUTATION_KEY")
    scenario_run.add_argument("--seed", type=int, default=1)
    scenario_run.add_argument("--store", type=Path, default=Path(".planguard"))


    plan_import = subcommands.add_parser("plan-import", help="Import and normalize a PostgreSQL FORMAT JSON plan")
    plan_import.add_argument("run_id")
    plan_import.add_argument("family_id")
    plan_import.add_argument("plan_path", type=Path)
    plan_import.add_argument("--store", type=Path, default=Path(".planguard"))
    plan_import.add_argument("--persist", action="store_true")

    compare = subcommands.add_parser("compare", help="Compare two captured runs with comparability checks")
    compare.add_argument("baseline_run_id")
    compare.add_argument("candidate_run_id")
    compare.add_argument("--store", type=Path, default=Path(".planguard"))
    compare.add_argument("--policy", type=Path)
    compare.add_argument("--persist", action="store_true")

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



def _key_values(items: list[str]) -> dict[str, object]:
    result: dict[str, object] = {}
    for item in items:
        if "=" not in item:
            raise ValueError(f"Expected KEY=JSON_VALUE, got {item!r}")
        key, raw = item.split("=", 1)
        result[key] = json.loads(raw)
    return result


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
                producer=ProducerIdentity(name="planguard", version="0.5.0", build="cli"),
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


        if args.command == "scenario-catalog":
            store = FilesystemArtifactStore(args.store)
            catalog = build_academic_catalog(producer=ProducerIdentity(name="planguard", version="0.5.0", build="cli"))
            count = catalog.persist(store)
            snapshot = catalog.registry.snapshot()
            print(json.dumps({"persisted": count, "templates": snapshot.template_keys, "bindings": snapshot.binding_keys, "mutations": snapshot.mutation_keys, "adapters": snapshot.adapter_keys}, indent=2))
            return 0

        if args.command in {"scenario-instantiate", "scenario-run"}:
            store = FilesystemArtifactStore(args.store)
            producer = ProducerIdentity(name="planguard", version="0.5.0", build="cli")
            catalog = build_academic_catalog(producer=producer)
            catalog.persist(store)
            if args.command == "scenario-run" and args.scenario_instance_id:
                instance = store.load(args.scenario_instance_id)
                if not isinstance(instance, ScenarioInstanceArtifact):
                    raise ValueError("scenario_instance_id must refer to a scenario_instance artifact")
            else:
                template_key = args.template if args.command == "scenario-run" else args.template_key
                binding_key = args.binding if args.command == "scenario-run" else args.binding_key
                if not template_key or not binding_key:
                    raise ValueError("Inline scenario execution requires --template and --binding")
                template = catalog.registry.require_template(template_key)
                binding = catalog.registry.require_binding(binding_key)
                mutation_specs = tuple((catalog.registry.require_mutation(key), {}) for key in args.mutation)
                instance = instantiate(template, binding, parameters=_key_values(args.parameter), variant_key=args.variant, mutations=mutation_specs, seed=args.seed, producer=producer)
                store.save(instance)
            if args.command == "scenario-instantiate":
                print(canonical_json_text(instance, pretty=True))
                return 0
            result = ScenarioRunner(registry=catalog.registry, store=store, producer=producer).run(instance)
            print(json.dumps({"scenario_run_id": result.scenario_run.artifact_id, "status": str(result.scenario_run.payload.status), "analysis_run_id": result.captured_run.manifest.artifact_id if result.captured_run else None, "oracle_evaluations": [item.model_dump(mode="json") for item in result.scenario_run.payload.oracle_evaluations]}, indent=2))
            return 0


        if args.command == "plan-import":
            store = FilesystemArtifactStore(args.store)
            family = store.load(args.family_id)
            if not isinstance(family, ObservedQueryFamilyArtifact):
                raise ValueError("family_id must refer to an observed_query_family artifact")
            raw = json.loads(args.plan_path.read_text(encoding="utf-8"))
            producer = ProducerIdentity(name="planguard", version="0.5.0", build="cli")
            plan, receipt = import_plan(raw_plan=raw, run_id=args.run_id, query_family_ref=family.reference(), producer=producer)
            evidence, findings = analyze_plan(plan, producer=producer)
            if args.persist:
                store.save(plan)
                store.save(receipt)
                for artifact in (*evidence, *findings):
                    store.save(artifact)
            print(canonical_json_text({
                "plan": plan.model_dump(mode="json"),
                "receipt": receipt.model_dump(mode="json"),
                "findings": [item.model_dump(mode="json") for item in findings],
            }, pretty=True))
            return 0

        if args.command == "compare":
            store = FilesystemArtifactStore(args.store)
            base_manifest, base = load_analysis_bundle(store, args.baseline_run_id)
            cand_manifest, cand = load_analysis_bundle(store, args.candidate_run_id)
            policy = None
            if args.policy:
                policy = default_codec.decode(args.policy.read_bytes())
                if not isinstance(policy, BudgetPolicyArtifact): raise ValueError("--policy must be a budget_policy artifact")
            producer = ProducerIdentity(name="planguard", version="0.5.0", build="cli")
            report = compare_runs(baseline_manifest=base_manifest, candidate_manifest=cand_manifest, baseline=base, candidate=cand, loader=store.load, producer=producer, baseline_plans=base.plan_observations, candidate_plans=cand.plan_observations, relative_policy=policy)
            if args.persist: store.save(report)
            print(canonical_json_text(report, pretty=True))
            failed = any(str(item.status) == "failed" for item in report.payload.relative_rule_evaluations)
            return 2 if failed else 0

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
