"use client";

import { Bar, BarChart, ResponsiveContainer, XAxis, YAxis, Tooltip, Cell } from "recharts";

interface StanceBarProps {
  data: { stance: string; count: number }[];
}

const COLOR: Record<string, string> = {
  positive: "#10b981",
  negative: "#ef4444",
  neutral: "#a1a1aa",
  mixed: "#f59e0b",
};

export function StanceBar({ data }: StanceBarProps) {
  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={data}>
        <XAxis dataKey="stance" stroke="#71717a" fontSize={12} />
        <YAxis stroke="#71717a" fontSize={12} allowDecimals={false} />
        <Tooltip cursor={{ fill: "rgba(255,255,255,0.04)" }} />
        <Bar dataKey="count">
          {data.map((d) => (
            <Cell key={d.stance} fill={COLOR[d.stance] ?? "#ef4444"} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
