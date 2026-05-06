"use client";

import { Bar, BarChart, ResponsiveContainer, XAxis, YAxis, Tooltip } from "recharts";

interface IntensityHistProps {
  data: { bucket: string; count: number }[];
}

export function IntensityHist({ data }: IntensityHistProps) {
  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={data}>
        <XAxis dataKey="bucket" stroke="#71717a" fontSize={12} />
        <YAxis stroke="#71717a" fontSize={12} allowDecimals={false} />
        <Tooltip />
        <Bar dataKey="count" fill="#dc2626" />
      </BarChart>
    </ResponsiveContainer>
  );
}
