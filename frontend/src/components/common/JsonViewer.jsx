import { useState } from 'react';

function JsonNode({ keyName, value, depth = 0 }) {
  const [collapsed, setCollapsed] = useState(depth > 1);
  const isObject = value !== null && typeof value === 'object';
  const isArray = Array.isArray(value);
  const indent = depth * 16;

  if (!isObject) {
    // 원시값 렌더링
    let display;
    let colorClass;
    if (typeof value === 'string') {
      display = `"${value}"`;
      colorClass = 'text-success';
    } else if (typeof value === 'number') {
      display = String(value);
      colorClass = 'text-primary-700';
    } else if (typeof value === 'boolean') {
      display = String(value);
      colorClass = 'text-warning';
    } else {
      display = 'null';
      colorClass = 'text-neutral-muted';
    }

    return (
      <div style={{ paddingLeft: indent }} className="flex gap-1 py-0.5 text-[0.8125rem] font-mono">
        {keyName !== null && <span className="text-error">{`"${keyName}"`}: </span>}
        <span className={colorClass}>{display}</span>
      </div>
    );
  }

  const entries = isArray
    ? value.map((v, i) => [i, v])
    : Object.entries(value);
  const bracket = isArray ? ['[', ']'] : ['{', '}'];
  const count = entries.length;

  return (
    <div style={{ paddingLeft: indent }}>
      <div
        className="flex items-center gap-1 py-0.5 cursor-pointer hover:bg-surface-hover rounded text-[0.8125rem] font-mono"
        onClick={() => setCollapsed(!collapsed)}
      >
        <span className="text-neutral-muted text-[0.625rem] w-3 text-center select-none">
          {collapsed ? '▶' : '▼'}
        </span>
        {keyName !== null && <span className="text-error">{`"${keyName}"`}: </span>}
        {collapsed ? (
          <span className="text-neutral-muted">{bracket[0]} {count}개 항목 {bracket[1]}</span>
        ) : (
          <span className="text-neutral-sub">{bracket[0]}</span>
        )}
      </div>
      {!collapsed && (
        <>
          {entries.map(([k, v]) => (
            <JsonNode key={k} keyName={isArray ? null : k} value={v} depth={depth + 1} />
          ))}
          <div style={{ paddingLeft: 0 }} className="text-[0.8125rem] font-mono text-neutral-sub py-0.5">
            {bracket[1]}
          </div>
        </>
      )}
    </div>
  );
}

export default function JsonViewer({ data, title = '원본 JSON' }) {
  const [open, setOpen] = useState(false);

  if (!data) return null;

  return (
    <div className="mt-3">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 text-xs text-neutral-muted hover:text-primary-700 transition"
      >
        <span className="text-[0.625rem]">{open ? '▼' : '▶'}</span>
        {title}
      </button>
      {open && (
        <div className="mt-2 p-3 rounded-md border border-neutral-divider bg-[#FAFAF8] overflow-x-auto max-h-[400px] overflow-y-auto">
          <JsonNode keyName={null} value={data} depth={0} />
        </div>
      )}
    </div>
  );
}
