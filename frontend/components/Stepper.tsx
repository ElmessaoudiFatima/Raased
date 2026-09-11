"use client";

import { Check } from "lucide-react";

export interface Step {
  title: string;
  subtitle?: string;
}

export function Stepper({
  steps,
  current,
}: {
  steps: Step[];
  current: number;
}) {
  return (
    <ol className="flex items-center">
      {steps.map((step, i) => {
        const done = i < current;
        const active = i === current;
        return (
          <li key={step.title} className="flex flex-1 items-center last:flex-none">
            <div className="flex items-center gap-2">
              <div
                className={[
                  "flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs font-bold transition-all",
                  done
                    ? "bg-emerald-500 text-white shadow-md shadow-emerald-500/20"
                    : active
                    ? "bg-blue-600 text-white ring-4 ring-blue-500/30 shadow-md shadow-blue-500/30 font-extrabold"
                    : "bg-slate-800 text-slate-400 border border-slate-700",
                ].join(" ")}
              >
                {done ? <Check className="h-4 w-4 stroke-[3]" /> : i + 1}
              </div>
              <div className="hidden sm:block whitespace-nowrap">
                <p className={`text-xs font-semibold leading-tight whitespace-nowrap ${active ? "text-white" : done ? "text-slate-300" : "text-slate-400"}`}>
                  {step.title}
                </p>
                {step.subtitle && (
                  <p className="text-[10px] text-slate-500 whitespace-nowrap">{step.subtitle}</p>
                )}
              </div>
            </div>
            {i < steps.length - 1 && (
              <span
                className={[
                  "mx-2 h-0.5 flex-1 transition-colors min-w-3 sm:min-w-6",
                  i < current ? "bg-emerald-500" : "bg-slate-800",
                ].join(" ")}
              />
            )}
          </li>
        );
      })}
    </ol>
  );
}