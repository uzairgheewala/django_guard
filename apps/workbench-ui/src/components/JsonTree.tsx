import { useState } from "react";

interface JsonTreeProps {
  value: unknown;
  name?: string;
  depth?: number;
}

function scalar(value: unknown): string {
  if (typeof value === "string") return JSON.stringify(value);
  if (value === null) return "null";
  return String(value);
}

export function JsonTree({ value, name, depth = 0 }: JsonTreeProps) {
  const [open, setOpen] = useState(depth < 2);
  const prefix = name === undefined ? null : <span className="json-key">{name}: </span>;

  if (value === null || typeof value !== "object") {
    return (
      <div className="json-row" style={{ paddingLeft: `${depth * 16}px` }}>
        {prefix}
        <span className={`json-${value === null ? "null" : typeof value}`}>{scalar(value)}</span>
      </div>
    );
  }

  const entries = Array.isArray(value)
    ? value.map((item, index) => [String(index), item] as const)
    : Object.entries(value as Record<string, unknown>);
  const label = Array.isArray(value) ? `Array(${entries.length})` : `Object(${entries.length})`;

  return (
    <div className="json-branch">
      <button
        type="button"
        className="json-toggle"
        style={{ marginLeft: `${depth * 16}px` }}
        onClick={() => setOpen((current) => !current)}
        aria-expanded={open}
      >
        <span aria-hidden="true">{open ? "▾" : "▸"}</span>
        {prefix}
        <span className="muted">{label}</span>
      </button>
      {open &&
        entries.map(([key, item]) => (
          <JsonTree key={key} value={item} name={key} depth={depth + 1} />
        ))}
    </div>
  );
}
