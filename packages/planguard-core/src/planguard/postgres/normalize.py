"""Normalize PostgreSQL JSON plans into stable semantic PlanGuard artifacts."""

from __future__ import annotations

import hashlib
from collections import Counter, defaultdict
from typing import Any, Iterable

from planguard.artifacts.models import PlanFeatures, PlanNode
from planguard.canonical import canonical_json_bytes

_KNOWN_KEYS = {
    "Node Type", "Parent Relationship", "Parallel Aware", "Async Capable", "Relation Name",
    "Alias", "Index Name", "Join Type", "Strategy", "Startup Cost", "Total Cost", "Plan Rows",
    "Plan Width", "Actual Startup Time", "Actual Total Time", "Actual Rows", "Actual Loops",
    "Rows Removed by Filter", "Shared Hit Blocks", "Shared Read Blocks", "Temp Read Blocks",
    "Temp Written Blocks", "Sort Method", "Sort Space Type", "Sort Space Used", "Peak Memory Usage",
    "Workers Planned", "Workers Launched", "Filter", "Index Cond", "Hash Cond", "Join Filter", "Plans",
}


def _num(value: Any, cast=float):
    if value is None:
        return None
    try:
        return cast(value)
    except (TypeError, ValueError):
        return None


def _extract_document(raw: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return (plan root, metadata) from PostgreSQL's common JSON forms."""
    if isinstance(raw, list):
        if not raw:
            raise ValueError("PostgreSQL plan document is empty")
        raw = raw[0]
    if not isinstance(raw, dict):
        raise TypeError("PostgreSQL plan must be a JSON object or one-element JSON array")
    if "Plan" in raw and isinstance(raw["Plan"], dict):
        return raw["Plan"], {key: value for key, value in raw.items() if key != "Plan"}
    if "Node Type" in raw:
        return raw, {}
    raise ValueError("PostgreSQL plan document has no Plan root")


def normalize_postgres_plan(raw: Any) -> tuple[str, tuple[PlanNode, ...], PlanFeatures, dict[str, Any]]:
    root, metadata = _extract_document(raw)
    nodes: list[PlanNode] = []
    depth_by_id: dict[str, int] = {}

    def visit(node: dict[str, Any], path: tuple[int, ...], depth: int) -> str:
        node_id = "plan-node:" + ("root" if not path else ".".join(str(item) for item in path))
        children = node.get("Plans") if isinstance(node.get("Plans"), list) else []
        child_ids = tuple(visit(child, path + (index,), depth + 1) for index, child in enumerate(children) if isinstance(child, dict))
        depth_by_id[node_id] = depth
        unknown = {key: value for key, value in node.items() if key not in _KNOWN_KEYS}
        nodes.append(
            PlanNode(
                node_id=node_id,
                node_type=str(node.get("Node Type", "Unknown")),
                relation=node.get("Relation Name"),
                alias=node.get("Alias"),
                index=node.get("Index Name"),
                join_type=node.get("Join Type"),
                strategy=node.get("Strategy"),
                estimated_startup_cost=_num(node.get("Startup Cost")),
                estimated_total_cost=_num(node.get("Total Cost")),
                estimated_rows=_num(node.get("Plan Rows")),
                estimated_width=_num(node.get("Plan Width"), int),
                actual_startup_ms=_num(node.get("Actual Startup Time")),
                actual_total_ms=_num(node.get("Actual Total Time")),
                actual_rows=_num(node.get("Actual Rows")),
                loops=_num(node.get("Actual Loops")),
                rows_removed_by_filter=_num(node.get("Rows Removed by Filter")),
                shared_hit_blocks=_num(node.get("Shared Hit Blocks"), int),
                shared_read_blocks=_num(node.get("Shared Read Blocks"), int),
                temp_read_blocks=_num(node.get("Temp Read Blocks"), int),
                temp_written_blocks=_num(node.get("Temp Written Blocks"), int),
                sort_method=node.get("Sort Method"),
                sort_space_type=node.get("Sort Space Type"),
                sort_space_kb=_num(node.get("Sort Space Used"), int),
                peak_memory_kb=_num(node.get("Peak Memory Usage"), int),
                workers_planned=_num(node.get("Workers Planned"), int),
                workers_launched=_num(node.get("Workers Launched"), int),
                filter=node.get("Filter"),
                index_condition=node.get("Index Cond"),
                hash_condition=node.get("Hash Cond"),
                join_filter=node.get("Join Filter"),
                child_node_ids=child_ids,
                unknown_attributes=unknown,
            )
        )
        return node_id

    root_id = visit(root, (), 0)
    # visit appends parents after descendants; sort by stable tree path.
    nodes.sort(key=lambda item: (item.node_id.count("."), item.node_id))
    counts = Counter(item.node_type for item in nodes)
    relation_access: dict[str, set[str]] = defaultdict(set)
    estimate_errors: list[float] = []
    nested_loop_rows = 0.0
    rows_removed = 0.0
    shared_hits = shared_reads = temp_blocks = 0
    indexes: set[str] = set()
    has_parallel = False
    has_spill = False
    for node in nodes:
        if node.relation:
            relation_access[node.relation].add(node.node_type)
        if node.index:
            indexes.add(node.index)
        if node.estimated_rows is not None and node.actual_rows is not None:
            estimated = max(node.estimated_rows, 1e-9)
            actual = max(node.actual_rows, 1e-9)
            estimate_errors.append(max(actual / estimated, estimated / actual))
        if node.node_type == "Nested Loop" and node.actual_rows is not None:
            nested_loop_rows += node.actual_rows * (node.loops or 1)
        rows_removed += node.rows_removed_by_filter or 0
        shared_hits += node.shared_hit_blocks or 0
        shared_reads += node.shared_read_blocks or 0
        temp_blocks += (node.temp_read_blocks or 0) + (node.temp_written_blocks or 0)
        has_spill = has_spill or bool(node.sort_space_type and node.sort_space_type.lower() == "disk") or bool((node.temp_read_blocks or 0) + (node.temp_written_blocks or 0))
        has_parallel = has_parallel or bool((node.workers_planned or 0) > 0 or (node.workers_launched or 0) > 0 or node.node_type.startswith("Parallel"))

    shape_material = [
        {
            "node_type": item.node_type,
            "relation": item.relation,
            "index": item.index,
            "join_type": item.join_type,
            "strategy": item.strategy,
            "children": item.child_node_ids,
        }
        for item in nodes
    ]
    fingerprint = "psh_" + hashlib.sha256(canonical_json_bytes(shape_material)).hexdigest()[:24]
    features = PlanFeatures(
        node_count=len(nodes),
        maximum_depth=max(depth_by_id.values(), default=0),
        node_type_counts=dict(sorted(counts.items())),
        relation_access={key: tuple(sorted(value)) for key, value in sorted(relation_access.items())},
        index_names=tuple(sorted(indexes)),
        maximum_estimate_error_ratio=max(estimate_errors) if estimate_errors else None,
        nested_loop_effective_rows=nested_loop_rows or None,
        rows_removed_by_filter=rows_removed,
        shared_hit_blocks=shared_hits,
        shared_read_blocks=shared_reads,
        temporary_io_blocks=temp_blocks,
        has_disk_spill=has_spill,
        has_parallelism=has_parallel,
        planning_time_ms=_num(metadata.get("Planning Time")),
        execution_time_ms=_num(metadata.get("Execution Time")),
        plan_shape_fingerprint=fingerprint,
    )
    return root_id, tuple(nodes), features, metadata


def iter_plan_nodes(root_id: str, nodes: Iterable[PlanNode]) -> Iterable[PlanNode]:
    by_id = {node.node_id: node for node in nodes}
    stack = [root_id]
    while stack:
        node_id = stack.pop()
        node = by_id[node_id]
        yield node
        stack.extend(reversed(node.child_node_ids))
