import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import type { ArtifactDocumentLike } from "../lib/api";

interface GraphNode {
  node_id: string;
  kind: string;
  label: string;
  artifact_ref?: { artifact_id: string } | null;
  attributes: Record<string, unknown>;
}

interface GraphEdge {
  edge_id: string;
  from_node: string;
  to_node: string;
  kind: string;
  confidence: number;
  inference_method: string;
  attributes: Record<string, unknown>;
}

interface Props {
  graphArtifact: ArtifactDocumentLike;
  episodes: ArtifactDocumentLike[];
  selectedArtifactId: string | null;
  onSelectArtifact: (artifactId: string | null) => void;
}

const kindOrder = ["operation", "transaction", "query_execution", "query_family", "finding", "episode"];
const kindLabels: Record<string, string> = {
  operation: "Operation",
  transaction: "Transactions",
  query_execution: "Executions",
  query_family: "Families",
  finding: "Findings",
  episode: "Episodes",
};

function numberValue(value: unknown): number {
  return typeof value === "number" ? value : 0;
}

export function WorkloadGraphExplorer({ graphArtifact, episodes, selectedArtifactId, onSelectArtifact }: Props) {
  const payload = graphArtifact.payload as unknown as { nodes: GraphNode[]; edges: GraphEdge[]; family_scheme_key: string };
  const [minimumConfidence, setMinimumConfidence] = useState(0.5);
  const [showExecutions, setShowExecutions] = useState(true);
  const [showTransactions, setShowTransactions] = useState(true);
  const [showInferred, setShowInferred] = useState(true);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  const projected = useMemo(() => {
    const allowedNodes = payload.nodes.filter((node) => {
      if (!showExecutions && node.kind === "query_execution") return false;
      if (!showTransactions && node.kind === "transaction") return false;
      return true;
    });
    const allowedIds = new Set(allowedNodes.map((node) => node.node_id));
    const edges = payload.edges.filter((edge) =>
      allowedIds.has(edge.from_node)
      && allowedIds.has(edge.to_node)
      && edge.confidence >= minimumConfidence
      && (showInferred || edge.inference_method !== "inferred"),
    );
    return { nodes: allowedNodes, edges };
  }, [minimumConfidence, payload.edges, payload.nodes, showExecutions, showInferred, showTransactions]);

  const layout = useMemo(() => {
    const grouped = new Map<string, GraphNode[]>();
    projected.nodes.forEach((node) => {
      const items = grouped.get(node.kind) ?? [];
      items.push(node);
      grouped.set(node.kind, items);
    });
    grouped.forEach((items) => items.sort((left, right) => {
      const leftSequence = numberValue(left.attributes.sequence_number ?? left.attributes.first_sequence);
      const rightSequence = numberValue(right.attributes.sequence_number ?? right.attributes.first_sequence);
      return leftSequence - rightSequence || left.node_id.localeCompare(right.node_id);
    }));
    const positions = new Map<string, { x: number; y: number }>();
    const visibleKinds = kindOrder.filter((kind) => grouped.has(kind));
    const columnWidth = visibleKinds.length > 1 ? 860 / (visibleKinds.length - 1) : 0;
    let maximumRows = 1;
    visibleKinds.forEach((kind, columnIndex) => {
      const items = grouped.get(kind) ?? [];
      maximumRows = Math.max(maximumRows, items.length);
      items.forEach((node, rowIndex) => positions.set(node.node_id, {
        x: 70 + columnIndex * columnWidth,
        y: 74 + rowIndex * 92,
      }));
    });
    return { grouped, positions, height: Math.max(360, 130 + maximumRows * 92), visibleKinds };
  }, [projected.nodes]);

  const selectedNode = projected.nodes.find((node) => node.node_id === selectedNodeId)
    ?? projected.nodes.find((node) => node.artifact_ref?.artifact_id === selectedArtifactId)
    ?? null;

  function choose(node: GraphNode) {
    setSelectedNodeId(node.node_id);
    onSelectArtifact(node.artifact_ref?.artifact_id ?? null);
  }

  return (
    <div className="graph-workbench">
      <div className="graph-controls">
        <label>
          Edge confidence ≥ {minimumConfidence.toFixed(2)}
          <input type="range" min="0" max="1" step="0.05" value={minimumConfidence} onChange={(event) => setMinimumConfidence(Number(event.target.value))} />
        </label>
        <label className="checkbox-row"><input type="checkbox" checked={showExecutions} onChange={(event) => setShowExecutions(event.target.checked)} />Executions</label>
        <label className="checkbox-row"><input type="checkbox" checked={showTransactions} onChange={(event) => setShowTransactions(event.target.checked)} />Transactions</label>
        <label className="checkbox-row"><input type="checkbox" checked={showInferred} onChange={(event) => setShowInferred(event.target.checked)} />Inferred edges</label>
        <span className="badge">{payload.family_scheme_key}</span>
      </div>

      <div className="graph-layout">
        <div className="graph-canvas" role="img" aria-label={`Workload graph with ${projected.nodes.length} nodes and ${projected.edges.length} edges`}>
          <svg viewBox={`0 0 1000 ${layout.height}`}>
            <defs>
              <marker id="arrow" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto"><path d="M0,0 L7,3.5 L0,7 z" /></marker>
            </defs>
            {layout.visibleKinds.map((kind, index) => {
              const x = 70 + index * (layout.visibleKinds.length > 1 ? 860 / (layout.visibleKinds.length - 1) : 0);
              return <text key={kind} x={x} y={28} className="graph-column-label" textAnchor="middle">{kindLabels[kind] ?? kind}</text>;
            })}
            {projected.edges.map((edge) => {
              const from = layout.positions.get(edge.from_node);
              const to = layout.positions.get(edge.to_node);
              if (!from || !to) return null;
              const selected = edge.from_node === selectedNode?.node_id || edge.to_node === selectedNode?.node_id;
              return <g key={edge.edge_id}>
                <line
                  x1={from.x + 48}
                  y1={from.y}
                  x2={to.x - 48}
                  y2={to.y}
                  className={`graph-edge edge-${edge.inference_method} ${selected ? "selected" : ""}`}
                  markerEnd="url(#arrow)"
                  opacity={0.35 + edge.confidence * 0.65}
                />
                {edge.inference_method === "inferred" && <text x={(from.x + to.x) / 2} y={(from.y + to.y) / 2 - 5} className="graph-edge-label" textAnchor="middle">{edge.kind} · {edge.confidence.toFixed(2)}</text>}
              </g>;
            })}
            {projected.nodes.map((node) => {
              const position = layout.positions.get(node.node_id);
              if (!position) return null;
              const selected = node.node_id === selectedNode?.node_id;
              return <g
                key={node.node_id}
                role="button"
                aria-label={node.label}
                className={`graph-node graph-node-${node.kind} ${selected ? "selected" : ""}`}
                transform={`translate(${position.x - 48}, ${position.y - 27})`}
                onClick={() => choose(node)}
              >
                <rect width="96" height="54" rx="10" />
                <text x="48" y="22" textAnchor="middle">{node.kind.replaceAll("query_", "")}</text>
                <text x="48" y="39" textAnchor="middle" className="graph-node-caption">{node.label.slice(0, 16)}</text>
              </g>;
            })}
          </svg>
        </div>

        <aside className="graph-inspector">
          <h3>Selection</h3>
          {selectedNode ? <>
            <span className="badge">{selectedNode.kind}</span>
            <h4>{selectedNode.label}</h4>
            {selectedNode.artifact_ref && <Link to={`/artifacts/${selectedNode.artifact_ref.artifact_id}`}>Open artifact</Link>}
            <dl className="compact-definition-list">
              {Object.entries(selectedNode.attributes).slice(0, 12).map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{typeof value === "object" ? JSON.stringify(value) : String(value ?? "—")}</dd></div>)}
            </dl>
          </> : <p className="muted">Select a node from the graph, timeline, or family list.</p>}
          <h3>Episodes</h3>
          <div className="episode-list">
            {episodes.map((episode) => {
              const episodePayload = episode.payload;
              const bindings = episodePayload.node_bindings as Record<string, string>;
              const active = selectedNode ? Object.values(bindings).includes(selectedNode.node_id) : false;
              return <button key={episode.artifact_id} type="button" className={`episode-row ${active ? "active" : ""}`} onClick={() => {
                const nodeId = Object.values(bindings)[0];
                const node = projected.nodes.find((candidate) => candidate.node_id === nodeId);
                if (node) choose(node);
              }}>
                <strong>{String(episodePayload.title)}</strong>
                <span>{String(episodePayload.motif_key)}</span>
                <small>{(numberValue(episodePayload.match_confidence) * 100).toFixed(0)}% match</small>
              </button>;
            })}
            {episodes.length === 0 && <p className="muted">No motif episodes matched this projection.</p>}
          </div>
        </aside>
      </div>
    </div>
  );
}
