import { useMemo, useState } from "react";
import type { ReactNode } from "react";
import type { ArtifactDocumentLike } from "../lib/api";

interface PlanNode {
  node_id: string;
  node_type: string;
  relation?: string | null;
  index?: string | null;
  join_type?: string | null;
  estimated_rows?: number | null;
  actual_rows?: number | null;
  actual_total_ms?: number | null;
  loops?: number | null;
  shared_read_blocks?: number | null;
  temp_read_blocks?: number | null;
  temp_written_blocks?: number | null;
  child_node_ids: string[];
}

function ratio(node: PlanNode): string {
  if (!node.estimated_rows || node.actual_rows == null) return "—";
  const a = Math.max(node.estimated_rows, 1e-9);
  const b = Math.max(node.actual_rows, 1e-9);
  return `${Math.max(a / b, b / a).toFixed(1)}×`;
}

export function PlanTree({ plan }: { plan: ArtifactDocumentLike }) {
  const [selected, setSelected] = useState<string>(String(plan.payload.root_node_id));
  const nodes = (plan.payload.nodes ?? []) as PlanNode[];
  const byId = useMemo(() => new Map(nodes.map((node) => [node.node_id, node])), [nodes]);
  const selectedNode = byId.get(selected);

  function renderNode(nodeId: string, depth = 0): ReactNode {
    const node = byId.get(nodeId);
    if (!node) return null;
    const spill = (node.temp_read_blocks ?? 0) + (node.temp_written_blocks ?? 0) > 0;
    return (
      <li key={node.node_id}>
        <button type="button" className={`plan-node-button ${selected === node.node_id ? "selected" : ""}`} onClick={() => setSelected(node.node_id)}>
          <span className="plan-branch" style={{ width: `${depth * 18}px` }} aria-hidden="true" />
          <span><strong>{node.node_type}</strong><small>{node.relation ?? node.join_type ?? "operator"}{node.index ? ` · ${node.index}` : ""}</small></span>
          <span>{node.actual_rows ?? node.estimated_rows ?? "—"} rows</span>
          <span>{node.actual_total_ms != null ? `${node.actual_total_ms.toFixed(2)} ms` : "estimated"}</span>
          {spill && <span className="badge severity-high">spill</span>}
        </button>
        {node.child_node_ids.length > 0 && <ul>{node.child_node_ids.map((child) => renderNode(child, depth + 1))}</ul>}
      </li>
    );
  }

  return (
    <div className="plan-tree-layout">
      <ol className="plan-tree">{renderNode(String(plan.payload.root_node_id))}</ol>
      <aside className="plan-node-inspector">
        <h3>Selected node</h3>
        {selectedNode ? <dl className="compact-definition-list">
          <div><dt>Operator</dt><dd>{selectedNode.node_type}</dd></div>
          <div><dt>Relation</dt><dd>{selectedNode.relation ?? "—"}</dd></div>
          <div><dt>Index</dt><dd>{selectedNode.index ?? "—"}</dd></div>
          <div><dt>Estimated rows</dt><dd>{selectedNode.estimated_rows ?? "—"}</dd></div>
          <div><dt>Actual rows</dt><dd>{selectedNode.actual_rows ?? "—"}</dd></div>
          <div><dt>Estimate error</dt><dd>{ratio(selectedNode)}</dd></div>
          <div><dt>Loops</dt><dd>{selectedNode.loops ?? "—"}</dd></div>
          <div><dt>Shared reads</dt><dd>{selectedNode.shared_read_blocks ?? 0}</dd></div>
        </dl> : <p>Select a plan node.</p>}
      </aside>
    </div>
  );
}
