"use client";

const styles: Record<string, string> = {
  LOW: "bg-slate-100 text-slate-600",
  MEDIUM: "bg-amber-100 text-amber-700",
  HIGH: "bg-orange-100 text-orange-700",
  CRITICAL: "bg-red-100 text-red-700",
  NORMAL: "bg-emerald-100 text-emerald-700",
  EVENT: "bg-amber-100 text-amber-700",
  INCIDENT: "bg-orange-100 text-orange-700",
  CRISIS: "bg-red-100 text-red-700",
};

export function AlertBadge({ level }: { level: string }) {
  return (
    <span className={`badge ${styles[level] || "bg-slate-100 text-slate-600"}`}>
      {level}
    </span>
  );
}

export default AlertBadge;