"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowRight, Eye, EyeOff, Lock, Mail } from "lucide-react";
import AuthShell from "@/components/AuthShell";
import { Button, Input } from "@/components/ui";
import { post } from "@/lib/api";
import { homeRoute, setSession, type User } from "@/lib/auth";
import { useLanguage } from "@/lib/i18n";

interface LoginResponse {
  access_token: string;
  user: User;
}

export default function LoginPage() {
  const router = useRouter();
  const { lang, changeLanguage, t, isRTL } = useLanguage();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const data = await post<LoginResponse>("/auth/login", { email, password });
      setSession(data.access_token, data.user);
      router.push(homeRoute(data.user.role));
    } catch (err) {
      setError(err instanceof Error ? err.message : t.loginError);
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthShell currentLang={lang} onLanguageChange={changeLanguage}>
      <div className={isRTL ? "text-right" : "text-left"}>
        <h2 className="text-2xl font-bold tracking-tight text-white">
          {t.welcome}
        </h2>
        <p className="mt-1.5 text-sm text-slate-400">
          {t.subtitle}
        </p>
      </div>

      <form onSubmit={submit} className="mt-7 space-y-4">
        <div>
          <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-slate-300">
            {t.emailLabel}
          </label>
          <div className="relative">
            <Mail className={`pointer-events-none absolute top-3 h-4 w-4 text-slate-500 ${isRTL ? "right-3.5" : "left-3.5"}`} />
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder={t.emailPlaceholder}
              required
              className={`w-full rounded-xl border border-slate-700/80 bg-[#0a101d] py-2.5 text-sm text-slate-100 placeholder:text-slate-500 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 ${
                isRTL ? "pr-10 pl-3.5" : "pl-10 pr-3.5"
              }`}
            />
          </div>
        </div>

        <div>
          <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-slate-300">
            {t.passwordLabel}
          </label>
          <div className="relative">
            <Lock className={`pointer-events-none absolute top-3 h-4 w-4 text-slate-500 ${isRTL ? "right-3.5" : "left-3.5"}`} />
            <input
              type={show ? "text" : "password"}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder={t.passwordPlaceholder}
              required
              className={`w-full rounded-xl border border-slate-700/80 bg-[#0a101d] py-2.5 text-sm text-slate-100 placeholder:text-slate-500 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 ${
                isRTL ? "pr-10 pl-11" : "pl-10 pr-11"
              }`}
            />
            <button
              type="button"
              onClick={() => setShow((s) => !s)}
              className={`absolute top-2.5 text-slate-400 hover:text-slate-200 transition ${isRTL ? "left-3" : "right-3"}`}
            >
              {show ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </button>
          </div>
        </div>

        <div className={`flex items-center text-xs ${isRTL ? "justify-start" : "justify-end"}`}>
          <Link
            href="/forgot-password"
            className="font-medium text-blue-400 hover:text-blue-300 transition hover:underline"
          >
            {t.forgotPassword}
          </Link>
        </div>

        {error && (
          <div className="rounded-xl border border-red-500/30 bg-red-950/40 px-4 py-3 text-sm font-medium text-red-300">
            {error}
          </div>
        )}

        <Button
          type="submit"
          variant="figma"
          loading={loading}
          className="w-full py-3 text-sm font-semibold shadow-lg shadow-blue-600/30"
        >
          {t.signIn}
          {!isRTL && <ArrowRight className="h-4 w-4 ml-1" />}
        </Button>
      </form>

      <p className="mt-7 text-center text-xs text-slate-400">
        {t.dontHaveAccount}{" "}
        <Link
          href="/register"
          className="font-semibold text-blue-400 hover:text-blue-300 hover:underline transition ml-1"
        >
          {t.signUpLink}
        </Link>
      </p>
    </AuthShell>
  );
}
