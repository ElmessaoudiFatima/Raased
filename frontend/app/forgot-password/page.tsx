"use client";

import { useRef, useState } from "react";
import Link from "next/link";
import { ArrowLeft, ArrowRight, CheckCircle2, KeyRound, Mail, RefreshCw } from "lucide-react";
import AuthShell from "@/components/AuthShell";
import { Button, Input } from "@/components/ui";
import { Stepper } from "@/components/Stepper";
import { post } from "@/lib/api";

const steps = [
  { title: "E-mail" },
  { title: "Code OTP" },
  { title: "Nouveau mot de passe" },
];

export default function ForgotPasswordPage() {
  const [step, setStep] = useState(0);
  const [email, setEmail] = useState("");
  const [codeInputs, setCodeInputs] = useState<string[]>(Array(6).fill(""));
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [token, setToken] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [resending, setResending] = useState(false);
  const [done, setDone] = useState(false);
  const [cooldown, setCooldown] = useState(0);
  const [devNotice, setDevNotice] = useState("");
  const refs = useRef<HTMLInputElement[]>([]);

  const startCooldown = () => {
    setCooldown(30);
    const iv = setInterval(() => {
      setCooldown((c) => {
        if (c <= 1) {
          clearInterval(iv);
          return 0;
        }
        return c - 1;
      });
    }, 1000);
  };

  const requestCode = async (resend = false) => {
    setError("");
    if (resend) setResending(true);
    else setLoading(true);
    try {
      let data: { message?: string; dev_code?: string } | undefined;
      if (resend) {
        data = await post<{ message: string; dev_code?: string }>("/auth/forgot-password/resend", { email });
      } else {
        data = await post<{ message: string; dev_code?: string }>("/auth/forgot-password", { email });
      }
      if (data?.dev_code) {
        setDevNotice(data.dev_code);
      }
      startCooldown();
      setStep(1);
      setTimeout(() => refs.current[0]?.focus(), 100);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Une erreur est survenue.");
    } finally {
      setLoading(false);
      setResending(false);
    }
  };

  const onCodeInput = (i: number, value: string) => {
    const digits = value.replace(/\D/g, "");
    const next = [...codeInputs];
    next[i] = digits.slice(-1);
    setCodeInputs(next);
    const full = next.join("");
    setCode(full);
    if (digits && i < 5) refs.current[i + 1]?.focus();
  };

  const onCodeKeyDown = (i: number, e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Backspace" && !codeInputs[i] && i > 0) {
      refs.current[i - 1]?.focus();
    }
  };

  const onCodePaste = (e: React.ClipboardEvent<HTMLInputElement>) => {
    e.preventDefault();
    const pasted = e.clipboardData.getData("text").replace(/\D/g, "").slice(0, 6);
    if (!pasted) return;
    const next = [...codeInputs];
    for (let i = 0; i < 6; i++) {
      next[i] = pasted[i] || "";
    }
    setCodeInputs(next);
    setCode(next.join(""));
    const nextFocusIdx = Math.min(pasted.length, 5);
    refs.current[nextFocusIdx]?.focus();
  };

  const verifyCode = async () => {
    setError("");
    setLoading(true);
    try {
      const data = await post<{ reset_token: string }>("/auth/forgot-password/verify", {
        email,
        code,
      });
      setToken(data.reset_token);
      setStep(2);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Code incorrect ou expiré.");
    } finally {
      setLoading(false);
    }
  };

  const resetPassword = async () => {
    setError("");
    setLoading(true);
    try {
      await post("/auth/forgot-password/reset", {
        reset_token: token,
        password,
        confirm_password: confirm,
      });
      setDone(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Impossible de réinitialiser le mot de passe.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthShell maxWidth="max-w-xl">
      <Link
        href="/login"
        className="mb-5 inline-flex items-center gap-1.5 text-xs font-medium text-slate-400 hover:text-blue-400 transition"
      >
        <ArrowLeft className="h-3.5 w-3.5" /> Retour à la connexion
      </Link>

      <div className="mb-6">
        <h2 className="text-2xl font-bold tracking-tight text-white">
          Mot de passe oublié
        </h2>
        <p className="mt-1 text-xs text-slate-400">
          Réinitialisez l'accès sécurisé à votre compte Raased
        </p>
      </div>

      {!done && (
        <div className="mb-6">
          <Stepper steps={steps} current={step} />
        </div>
      )}

      {done ? (
        <div className="text-center py-4">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-emerald-500/20 text-emerald-400 ring-1 ring-emerald-500/30">
            <CheckCircle2 className="h-8 w-8" />
          </div>
          <h3 className="mt-4 text-xl font-bold text-white">
            Mot de passe mis à jour !
          </h3>
          <p className="mt-2 text-xs text-slate-400">
            Votre nouveau mot de passe est actif. Vous pouvez vous reconnecter.
          </p>
          <Link href="/login" className="mt-6 inline-block w-full">
            <Button variant="figma" className="w-full py-3">
              Se connecter <ArrowRight className="h-4 w-4 ml-1" />
            </Button>
          </Link>
        </div>
      ) : (
        <>
          {step === 0 && (
            <div className="space-y-4">
              <div>
                <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-slate-300">
                  Adresse e-mail
                </label>
                <div className="relative">
                  <Mail className="pointer-events-none absolute left-3.5 top-3 h-4 w-4 text-slate-500" />
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="votre@email-professionnel.com"
                    required
                    className="w-full rounded-xl border border-slate-700/80 bg-[#0a101d] py-2.5 pl-10 pr-3.5 text-sm text-slate-100 placeholder:text-slate-500 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                  />
                </div>
              </div>

              {error && (
                <div className="rounded-xl border border-red-500/30 bg-red-950/40 px-4 py-3 text-xs font-medium text-red-300">
                  {error}
                </div>
              )}

              <Button
                type="button"
                variant="figma"
                onClick={() => requestCode(false)}
                loading={loading}
                disabled={!email.includes("@")}
                className="w-full py-3"
              >
                Envoyer le code OTP <ArrowRight className="h-4 w-4 ml-1" />
              </Button>
            </div>
          )}

          {step === 1 && (
            <div className="space-y-5 text-center">
              <div>
                <h3 className="text-base font-bold text-white">Saisissez le code à 6 chiffres</h3>
                <p className="mt-1 text-xs text-slate-400">
                  Code envoyé à <span className="font-semibold text-slate-200">{email}</span>
                </p>
              </div>

              <div className="flex justify-center gap-2 sm:gap-3 py-2">
                {codeInputs.map((val, idx) => (
                  <input
                    key={idx}
                    ref={(el) => {
                      if (el) refs.current[idx] = el;
                    }}
                    type="text"
                    inputMode="numeric"
                    maxLength={1}
                    value={val}
                    onChange={(e) => onCodeInput(idx, e.target.value)}
                    onKeyDown={(e) => onCodeKeyDown(idx, e)}
                    onPaste={idx === 0 ? onCodePaste : undefined}
                    className="h-12 w-11 sm:h-14 sm:w-12 rounded-xl border border-slate-700 bg-[#0a101d] text-center text-xl font-mono font-bold text-white outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/30"
                  />
                ))}
              </div>

              {devNotice && (
                <div className="rounded-xl border border-emerald-500/30 bg-emerald-950/30 p-3.5 text-left text-xs text-emerald-300 flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-lg">
                  <div>
                    <p className="font-semibold text-emerald-200">Code de vérification (Simulation / Local) :</p>
                    <p className="font-mono text-base font-bold text-white tracking-widest mt-0.5">{devNotice}</p>
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      const digits = devNotice.slice(0, 6).split("");
                      setCodeInputs(digits);
                      setCode(devNotice);
                    }}
                    className="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold shadow transition whitespace-nowrap self-start sm:self-auto"
                  >
                    Remplir automatiquement
                  </button>
                </div>
              )}

              {error && (
                <div className="rounded-xl border border-red-500/30 bg-red-950/40 px-4 py-3 text-xs font-medium text-red-300">
                  {error}
                </div>
              )}

              <div className="space-y-3 pt-2">
                <Button
                  type="button"
                  variant="figma"
                  onClick={verifyCode}
                  loading={loading}
                  disabled={code.length !== 6}
                  className="w-full py-3"
                >
                  Vérifier le code <ArrowRight className="h-4 w-4 ml-1" />
                </Button>

                <button
                  type="button"
                  onClick={() => requestCode(true)}
                  disabled={resending || cooldown > 0}
                  className="text-xs font-medium text-slate-400 hover:text-blue-400 disabled:opacity-50 transition"
                >
                  {cooldown > 0 ? `Renvoyer le code dans ${cooldown}s` : "Renvoyer le code"}
                </button>
              </div>
            </div>
          )}

          {step === 2 && (
            <div className="space-y-4">
              <div>
                <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-slate-300">
                  Nouveau mot de passe
                </label>
                <div className="relative">
                  <KeyRound className="pointer-events-none absolute left-3.5 top-3 h-4 w-4 text-slate-500" />
                  <input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="8 caractères minimum"
                    minLength={8}
                    required
                    className="w-full rounded-xl border border-slate-700/80 bg-[#0a101d] py-2.5 pl-10 pr-3.5 text-sm text-slate-100 placeholder:text-slate-500 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                  />
                </div>
              </div>

              <div>
                <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-slate-300">
                  Confirmer le mot de passe
                </label>
                <input
                  type="password"
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  placeholder="Répétez le mot de passe"
                  minLength={8}
                  required
                  className="w-full rounded-xl border border-slate-700/80 bg-[#0a101d] px-3.5 py-2.5 text-sm text-slate-100 placeholder:text-slate-500 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                />
              </div>

              {error && (
                <div className="rounded-xl border border-red-500/30 bg-red-950/40 px-4 py-3 text-xs font-medium text-red-300">
                  {error}
                </div>
              )}

              <Button
                type="button"
                variant="figma"
                onClick={resetPassword}
                loading={loading}
                disabled={password.length < 8 || password !== confirm}
                className="w-full py-3"
              >
                Valider le nouveau mot de passe <ArrowRight className="h-4 w-4 ml-1" />
              </Button>
            </div>
          )}
        </>
      )}
    </AuthShell>
  );
}
