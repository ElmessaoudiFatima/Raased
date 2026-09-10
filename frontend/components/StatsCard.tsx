"use client";

export function StatsCard({
  icon,
  label,
  value,
  accent = "teal",
  sub,
}: {
  icon: React.ReactNode;
  label: string;
  value: string | number;
  accent?: "teal" | "navy" | "amber" | "red" | "emerald";
  sub?: string;
}) {
  const accents = {
    teal: "bg-teal-50 text-raased-teal",
    navy: "bg-raased-navy/5 text-raased-navy",
    amber: "bg-amber-50 text-amber-600",
    red: "bg-red-50 text-raased-alert",
    emerald: "bg-emerald-50 text-emerald-600",
  };
  return (
    <div className="card flex items-start gap-4 p-5">
      <div className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl ${accents[accent]}`}>
        {icon}
      </div>
      <div className="min-w-0">
        <p className="text-2xl font-extrabold text-raased-navy">{value}</p>
        <p className="truncate text-sm font-medium text-slate-500">{label}</p>
        {sub && <p className="text-xs text-slate-400">{sub}</p>}
      </div>
    </div>
  );
}