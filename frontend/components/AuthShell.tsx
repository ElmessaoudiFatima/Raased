"use client";

import { Logo } from "./Logo";
import { LanguageSelector } from "./LanguageSelector";
import { useLanguage, Language } from "@/lib/i18n";
import { ShieldCheck } from "lucide-react";

export function AuthShell({
  children,
  currentLang,
  onLanguageChange,
  showLogo = true,
  maxWidth = "max-w-md",
}: {
  children: React.ReactNode;
  currentLang?: Language;
  onLanguageChange?: (lang: Language) => void;
  showLogo?: boolean;
  maxWidth?: string;
}) {
  const internalLang = useLanguage();
  const lang = currentLang ?? internalLang.lang;
  const setLang = onLanguageChange ?? internalLang.changeLanguage;

  return (
    <div className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden bg-[#0a101d] px-4 py-12 text-slate-100 selection:bg-blue-600 selection:text-white">
      {/* Dynamic moving background glow & grid */}
      <div className="pointer-events-none absolute -top-24 left-1/4 h-[500px] w-[500px] rounded-full bg-blue-600/25 blur-[120px] animate-orb-1" />
      <div className="pointer-events-none absolute -bottom-24 right-1/4 h-[450px] w-[450px] rounded-full bg-cyan-500/20 blur-[130px] animate-orb-2" />
      <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(to_right,rgba(255,255,255,0.03)_1px,transparent_1px),linear-gradient(to_bottom,rgba(255,255,255,0.03)_1px,transparent_1px)] bg-[size:36px_36px] animate-grid-drift [mask-image:radial-gradient(ellipse_60%_50%_at_50%_40%,#000_70%,transparent_100%)]" />

      {/* Top language selector pill */}
      <div className={`relative z-20 mb-6 flex w-full ${maxWidth} justify-end`}>
        <LanguageSelector currentLang={lang} onLanguageChange={setLang} />
      </div>

      {/* Brand logo */}
      {showLogo && (
        <div className="relative z-10 mb-8 flex flex-col items-center text-center">
          <Logo dark size="lg" />
        </div>
      )}

      {/* Main card matching Figma */}
      <div
        className={`relative z-10 w-full ${maxWidth} rounded-2xl border border-slate-800/80 bg-[#0f172a]/90 p-7 sm:p-8 shadow-2xl shadow-black/60 backdrop-blur-xl ring-1 ring-white/5 transition-all`}
      >
        {children}
      </div>

      {/* Bottom footer reassurance */}
      <div className="relative z-10 mt-8 flex items-center justify-center gap-2 text-xs text-slate-500">
        <ShieldCheck className="h-4 w-4 text-blue-400" />
        <span>Raased AI Network Intelligence — Conforme GSMA Open Gateway CAMARA</span>
      </div>
    </div>
  );
}

export default AuthShell;
