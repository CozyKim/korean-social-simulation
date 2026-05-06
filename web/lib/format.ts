const PERCENT = new Intl.NumberFormat("ko-KR", {
  style: "percent",
  maximumFractionDigits: 1,
});

const NUMBER = new Intl.NumberFormat("ko-KR", { maximumFractionDigits: 2 });

export const formatPercent = (v: number) => PERCENT.format(v);
export const formatNumber = (v: number) => NUMBER.format(v);

export function formatRelativeKo(iso: string): string {
  const d = new Date(iso);
  const diff = (Date.now() - d.getTime()) / 1000;
  if (diff < 60) return "방금 전";
  if (diff < 3600) return `${Math.floor(diff / 60)}분 전`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}시간 전`;
  return `${Math.floor(diff / 86400)}일 전`;
}
