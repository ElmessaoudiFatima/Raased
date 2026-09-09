"use client";

import { Language } from "@/lib/i18n";
import { Globe } from "lucide-react";

interface LanguageSelectorProps {
  currentLang: Language;
  onLanguageChange: (lang: Language) => void;
  showIcon?: boolean;
  className?: string;
}

const LANGUAGES: { code: Language; label: string }[] = [
  { code: "AR", label: "العربية" },
  { code: "FR", label: "FR" },
  { code: "EN", label: "EN" },
];

export function LanguageSelector({
  currentLang,
  onLanguageChange,
  showIcon = true,
  className = "",
}: LanguageSelectorProps) {
  return (
    <div
      className={`inline-flex items-center gap-1 rounded-xl border border-slate-800 bg-[#0f172a]/90 p-1 shadow-lg backdrop-blur-md ${className}`}
    >
      {showIcon && (
        <span className="flex h-6 w-6 items-center justify-center text-slate-400 pl-1">
          <Globe className="h-3.5 w-3.5" />
        </span>
      )}
      <div className="flex items-center gap-0.5">
        {LANGUAGES.map((l) => {
          const isActive = currentLang === l.code;
          return (
            <button
              key={l.code}
              type="button"
              onClick={() => onLanguageChange(l.code)}
              className={`rounded-lg px-2.5 py-1 text-xs font-semibold transition-all duration-200 ${
                isActive
                  ? "bg-figma-blue text-white shadow-md shadow-blue-600/30 ring-1 ring-blue-400/40"
                  : "text-slate-400 hover:bg-slate-800/60 hover:text-slate-200"
              }`}
            >
              {l.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

export default LanguageSelector;
