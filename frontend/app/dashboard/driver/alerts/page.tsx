"use client";

import { useEffect, useState } from "react";
import {
  AlertTriangle,
  Bot,
  CheckCircle2,
  Clock,
  Compass,
  Navigation,
  RefreshCw,
  ShieldAlert,
  Sparkles,
  Zap,
} from "lucide-react";
import { Topbar } from "@/components/Topbar";
import { Badge, Button, Card, EmptyState, Spinner } from "@/components/ui";
import { useShell } from "@/components/ShellContext";
import { useToast } from "@/components/Toasts";
import { get, patch } from "@/lib/api";

interface DriverAlert {
  id: string;
  severity: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
  title: string;
  message: string;
  status: string;
  created_at?: string | null;
  cargo_reference?: string | null;
}

export default function DriverAlertsPage() {
  const { openMobileMenu } = useShell();
  const { notify } = useToast();

  const [alerts, setAlerts] = useState<DriverAlert[]>([]);
  const [loading, setLoading] = useState(true);
  const [ackId, setAckId] = useState<string | null>(null);

  const load = () => {
    setLoading(true);
    get<{ alerts: DriverAlert[] }>("/drivers/alerts")
      .then((d) => setAlerts(d.alerts))
      .catch(() => notify("Impossible de charger les alertes.", "error"))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const acknowledge = async (id: string) => {
    setAckId(id);
    try {
      await patch(`/drivers/alerts/${id}/acknowledge`);
      notify("Alerte prise en compte par le chauffeur.");
      setAlerts((prev) =>
        prev.map((a) => (a.id === id ? { ...a, status: "ACKNOWLEDGED" } : a))
      );
    } catch (err) {
      notify(err instanceof Error ? err.message : "Erreur de validation.", "error");
    } finally {
      setAckId(null);
    }
  };

  const getSeverityBadge = (sev: string) => {
    switch (sev) {
      case "CRITICAL":
        return "bg-red-500/20 text-red-300 border-red-500/30";
      case "HIGH":
        return "bg-amber-500/20 text-amber-300 border-amber-500/30";
      case "MEDIUM":
        return "bg-yellow-500/20 text-yellow-300 border-yellow-500/30";
      default:
        return "bg-blue-500/20 text-blue-300 border-blue-500/30";
    }
  };

  return (
    <div>
      <Topbar
        title="Alertes & Consignes de l'Agent IA"
        subtitle="Notifications critiques, conditions de circulation et recommandations de pilotage"
        onMenu={openMobileMenu}
      />

      <div className="p-6 space-y-6">
        <div className="flex items-center justify-between">
          <p className="text-sm text-slate-400">
            {alerts.length} alerte(s) répertoriée(s) pour votre convoi
          </p>
          <Button variant="outline" size="sm" onClick={load} loading={loading}>
            <RefreshCw className="h-3.5 w-3.5 mr-1" /> Actualiser
          </Button>
        </div>

        {/* AI Copilot Suggestion Card */}
        <Card className="p-5 border-blue-500/30 bg-blue-950/20 space-y-3">
          <div className="flex items-center gap-2.5 text-blue-300">
            <Sparkles className="h-5 w-5 text-amber-400" />
            <h3 className="font-bold text-sm">Copilote IA Raased — Recommandation active</h3>
          </div>
          <p className="text-xs text-slate-300 leading-relaxed">
            « Ralentissement important signalé aux abords de Settat. Le profil CAMARA QoD a été automatiquement renforcé pour garantir votre liaison télématique. Suivez l'itinéraire recommandé sur votre carte pour économiser 22 minutes de trajet. »
          </p>
        </Card>

        {/* Alerts List */}
        {loading ? (
          <div className="flex h-64 items-center justify-center">
            <Spinner />
          </div>
        ) : alerts.length === 0 ? (
          <Card className="p-8 border-slate-800 bg-[#0f172a]">
            <EmptyState
              icon={<CheckCircle2 className="h-10 w-10 text-emerald-400" />}
              title="Aucune anomalie signalée"
              description="Votre convoi progresse dans les conditions nominales de sécurité et de délai."
            />
          </Card>
        ) : (
          <div className="space-y-3">
            {alerts.map((a) => (
              <Card
                key={a.id}
                className="p-5 border-slate-800 bg-[#0f172a] hover:border-slate-700 transition space-y-3 shadow-lg"
              >
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-slate-900 border border-slate-800">
                      <AlertTriangle className="h-5 w-5 text-amber-400" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <h4 className="font-bold text-white text-sm">{a.title}</h4>
                        <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-bold border ${getSeverityBadge(a.severity)}`}>
                          {a.severity}
                        </span>
                      </div>
                      {a.cargo_reference && (
                        <p className="text-xs text-slate-400 mt-0.5">
                          Cargaison concernée : <strong className="text-slate-200">{a.cargo_reference}</strong>
                        </p>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-3 self-end sm:self-center">
                    {a.status === "ACKNOWLEDGED" ? (
                      <span className="inline-flex items-center gap-1 rounded-lg bg-emerald-500/10 px-2.5 py-1 text-xs font-semibold text-emerald-400 border border-emerald-500/20">
                        <CheckCircle2 className="h-3.5 w-3.5" /> Prise en compte
                      </span>
                    ) : (
                      <Button
                        variant="figma"
                        size="sm"
                        loading={ackId === a.id}
                        onClick={() => acknowledge(a.id)}
                        className="text-xs"
                      >
                        Acquitter l'alerte
                      </Button>
                    )}
                  </div>
                </div>

                <p className="text-xs text-slate-300 leading-relaxed bg-[#0a101d] p-3 rounded-xl border border-slate-800">
                  {a.message}
                </p>

                {a.created_at && (
                  <p className="text-[11px] text-slate-500 flex items-center gap-1">
                    <Clock className="h-3 w-3" /> Reçue le {new Date(a.created_at).toLocaleString("fr-FR")}
                  </p>
                )}
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
