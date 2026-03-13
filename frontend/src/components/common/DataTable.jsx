export default function DataTable({ columns, data, onRowClick }) {
  return (
    <table className="w-full border-collapse">
      <thead>
        <tr>
          {columns.map((col) => (
            <th key={col.key} className={`text-left px-4 py-2.5 text-xs font-semibold text-neutral-sub border-b-2 border-neutral-divider bg-surface-hover whitespace-pre-line ${col.headerClassName || ''}`}>
              {col.label}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {data.map((row, i) => (
          <tr key={i} className="hover:bg-surface-hover cursor-pointer transition" onClick={() => onRowClick?.(row)}>
            {columns.map((col) => (
              <td key={col.key} className={`px-4 py-3 text-[0.8125rem] text-neutral-main border-b border-neutral-divider ${col.className || ''}`}>
                {col.render ? col.render(row[col.key], row) : row[col.key]}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
