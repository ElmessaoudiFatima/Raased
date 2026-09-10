"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { ArrowRight, CheckCircle2, KeyRound, UserPlus, AlertCircle } from "lucide-react";
import AuthShell from "@/components/AuthShell";
import { Button, Input, Spinner } from "@/components/ui";
import { get, post } from "@/lib/api";

export default function SetPasswordPage() {
  return (
    <Suspense
      fallback={
        <AuthShell>
          <div className="flex items-center justify-center py-16">
            <Spinner className="h-8 w-8 text-blue-500" />
          </div>
        </AuthShell>
      }
    >
      <Inner />
    </Suspense>
  );
}

function Inner() {
  const params = useSearchParams();
  const token = params.get("token") || "";

  const [state, setState] = useState<"loading" | "invalid" | "ready" | "done">("loading");
  const [info, setInfo] = useState<{
    first_name: string;
    last_name: string;
    email: string;
    role: string;
    organization_name?: string;
  } | null>(null);
  const [error, setError] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!token) {
      setState("invalid");
      return;
    }
    get<{
      valid: boolean;
      first_name: string;
      last_name: string;
      email: string;
      role: string;
      organization_name?: string | null;
    }>(`/auth/invitations/validate?token=${encodeURIComponent(token)}`)
      .then((data) => {
        setInfo({
          first_name: data.first_name,
          last_name: data.last_name,
          email: data.email,
          role: data.role,
          organization_name: data.organization_name || undefined,
        });
        setState("ready");
      })
      .catch(() => setState("invalid"));
  }, [token]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await post("/auth/invitations/accept", {
        token,
        password,
        confirm_password: confirm,
      });
      setState("done");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Impossible d'activer le compte.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthShell>
      {state === "loading" && (
        <div className="flex flex-col items-center gap-4 py-16 text-center">
          <Spinner className="h-8 w-8 text-blue-500" />
          <p className="text-sm text-slate-400">Vérification de votre invitation…</p>
        </div>
      )}

      {state === "invalid" && (
        <div className="text-center">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-red-500/20 text-red-400 ring-1 ring-red-500/30">
            <AlertCircle className="h-6 w-6" />
          </div>
          <h2 className="mt-4 text-xl font-bold text-white">Invitation invalide ou expirée</h2>
          <p className="mt-2 text-xs text-slate-400">
            Ce lien est invalide, expiré (48h) ou a déjà été utilisé. Votre manager peut vous renvoyer une nouvelle invitation.
          </p>
          <Link href="/login" className="mt-6 inline-block w-full">
            <Button variant="figma" className="w-full py-3">
              Retour à la connexion
            </Button>
          </Link>
        </div>
      )}

      {state === "done" && (
        <div className="text-center">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-emerald-500/20 text-emerald-400 ring-1 ring-emerald-500/30">
            <CheckCircle2 className="h-8 w-8" />
          </div>
          <h2 className="mt-4 text-xl font-bold text-white">Compte activé avec succès !</h2>
          <p className="mt-2 text-xs text-slate-400">
            Votre mot de passe a été configuré. Vous pouvez désormais vous connecter à la plateforme Raased.
          </p>
          <Link href="/login" className="mt-6 inline-block w-full">
            <Button variant="figma" className="w-full py-3">
              Se connecter <ArrowRight className="h-4 w-4 ml-1" />
            </Button>
          </Link>
        </div>
      )}

      {state === "ready" && info && (
        <>
          <div className="rounded-xl border border-blue-500/30 bg-blue-950/30 p-4 text-sm">
            <div className="flex items-start gap-3">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-blue-600/30 text-blue-400">
                <UserPlus className="h-4 w-4" />
              </div>
              <div className="text-xs text-slate-300">
                <p>
                  Bonjour <b className="text-white">{info.first_name} {info.last_name}</b>,
                </p>
                <p className="mt-1 text-slate-300">
                  {info.role === "MANAGER" ? (
                    <>Vous êtes invité(e) par <b className="text-blue-400">{info.organization_name || "votre entreprise"}</b> en tant que <b>Manager</b>.</>
                  ) : (
                    <>Vous êtes invité(e) par <b className="text-blue-400">{info.organization_name || "votre entreprise"}</b> en tant que <b>Chauffeur</b>.</>
                  )}
                </p>
                <p className="mt-1 font-mono text-[11px] text-slate-400">{info.email}</p>
              </div>
            </div>
          </div>

          <form onSubmit={submit} className="mt-6 space-y-4">
            <div>
              <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-slate-300">
                Créer votre mot de passe
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
                placeholder="Répéter le mot de passe"
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
              type="submit"
              variant="figma"
              loading={loading}
              disabled={password.length < 8 || password !== confirm}
              className="w-full py-3 text-sm font-semibold shadow-lg shadow-blue-600/30"
            >
              Activer mon compte & Accéder <ArrowRight className="h-4 w-4 ml-1" />
            </Button>
          </form>
        </>
      )}
    </AuthShell>
  );
}
