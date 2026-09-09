"use client";

import { MapPin, Radar } from "lucide-react";

export function Logo({
  dark = true,
  size = "md",
}: {
  dark?: boolean;
  size?: "sm" | "md" | "lg";
}) {
  const text =
    size === "lg" ? "text-3xl" : size === "sm" ? "text-lg" : "text-2xl";
  const sub = size === "lg" ? "text-sm" : "text-xs";
  return (
    <div className="flex items-center gap-3">
      <div
        className={[
          "flex items-center justify-center rounded-xl bg-gradient-to-br from-blue-500 to-blue-700 text-white shadow-lg shadow-blue-600/40 ring-1 ring-blue-400/30",
          size === "lg" ? "h-12 w-12" : size === "sm" ? "h-8 w-8" : "h-10 w-10",
        ].join(" ")}
      >
        <Radar className={size === "lg" ? "h-6 w-6" : size === "sm" ? "h-4 w-4" : "h-5 w-5"} />
      </div>
      <div className="leading-tight">
        <div className={`font-extrabold tracking-tight ${text} ${dark ? "text-white" : "text-slate-900"}`}>
          Raased <span className="text-blue-400 font-semibold text-lg ml-1">راصد</span>
        </div>
        <div className={`${sub} font-medium ${dark ? "text-slate-400" : "text-slate-500"}`}>
          AI Logistics Corridor Resilience
        </div>
      </div>
    </div>
  );
}

export function PinIcon({ className = "" }: { className?: string }) {
  return <MapPin className={className} />;
}