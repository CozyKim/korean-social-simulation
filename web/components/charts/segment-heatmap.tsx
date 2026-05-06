"use client";

interface Cell {
  row: string;
  col: string;
  value: number;
}

interface SegmentHeatmapProps {
  rows: string[];
  cols: string[];
  cells: Cell[];
}

export function SegmentHeatmap({ rows, cols, cells }: SegmentHeatmapProps) {
  const map = new Map(cells.map((c) => [`${c.row}|${c.col}`, c.value]));
  const max = Math.max(...cells.map((c) => Math.abs(c.value)), 0.01);
  return (
    <div className="overflow-auto">
      <table className="text-xs">
        <thead>
          <tr>
            <th className="px-2 py-1 text-left" />
            {cols.map((c) => (
              <th key={c} className="px-2 py-1 text-center text-zinc-400">
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r}>
              <th className="px-2 py-1 text-left text-zinc-400">{r}</th>
              {cols.map((c) => {
                const v = map.get(`${r}|${c}`) ?? 0;
                const intensity = Math.min(1, Math.abs(v) / max);
                const bg =
                  v >= 0
                    ? `rgba(16,185,129,${intensity.toFixed(2)})`
                    : `rgba(239,68,68,${intensity.toFixed(2)})`;
                return (
                  <td key={c} className="px-2 py-1 text-center tabular-nums" style={{ background: bg }}>
                    {v.toFixed(2)}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
