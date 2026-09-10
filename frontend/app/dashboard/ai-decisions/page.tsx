"use client";

import { useEffect, useState } from "react";
import {
  AlertTriangle,
  Bot,
  CheckCircle2,
  Cpu,
  Filter,
  Navigation,
  Radio,
  RefreshCw,
  Search,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Truck,
  Zap,
} from "lucide-react";
import { Topbar } from "@/components/Topbar";
import { Badge, Button, Card, EmptyState, Spinner } from "@/components/ui";
import { useShell } from "@/components/ShellContext";
import { useToast } from "@/components/Toasts";
import { get } from "@/lib/api";

interface AIDecision {
  id: string;
  driver_id?: string | null;
  driver_name: string;
  cargo_reference: string;
  corridor: string;
  type: string;
  severity: "INFO" | "WARNING" | "CRITICAL";
  status: "EXECUTED" | "ACTIVE" | "PENDING_CONFIRMATION";
  title: string;
  reason: string;
  recommendation: string;
  confidence: number;
  timestamp: string;
  telecom_node?: string;
}

export default function AIDecisionsPage() {
  const { openMobileMenu } = useShell();
  const { notify } = useToast();

  const [decisions, setDecisions] = useState<AIDecision[]>([]);
  const [loading, setLoading] = useState(true);
  const [driverFilter, setDriverFilter] = useState("ALL");
  const [typeFilter, setTypeFilter] = useState("ALL");
  const [actionId, setActionId] = useState<string | null>(null);

  const load = () => {
    setLoading(true);
    get<{ decisions: AIDecision[] }>("/managers/ai-decisions")
      .then((d) => setDecisions(d.decisions))
      .catch(() => notify("Impossible de charger les décisions IA.", "error"))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const applyDecision = (id: string, title: string) => {
    setActionId(id);
    setTimeout(() => {
      setDecisions((prev) =>
        prev.map((d) => (d.id === id ? { ...d, status: "EXECUTED" } : d))
      );
      setActionId(null);
      notify(`Action validée : ${title}`);
    }, 600);
  };

  const driverNames = Array.from(new Set(decisions.map((d) => d.driver_name))).filter(Boolean);

  const filtered = decisions.filter((d) => {
    const matchesDriver = driverFilter === "ALL" || d.driver_name === driverFilter;
    const matchesType = typeFilter === "ALL" || d.type === typeFilter;
    return matchesDriver && matchesType;
  });

  const getSeverityBadge = (sev: string) => {
    switch (sev) {
      case "CRITICAL":
        return "bg-red-500/20 text-red-300 border-red-500/30";
      case "WARNING":
        return "bg-amber-500/20 text-amber-300 border-amber-500/30";
      default:
        return "bg-blue-500/20 text-blue-300 border-blue-500/30";
    }
  };

  const getTypeIcon = (type: string) => {
    switch (type) {
      case "REROUTE":
        return <Navigation className="h-5 w-5 text-amber-400" />;
      case "QOD_BOOST":
        return <Zap className="h-5 w-5 text-cyan-400" />;
      case "SIM_SWAP_VERIFY":
        return <ShieldCheck className="h-5 w-5 text-emerald-400" />;
      default:
        return <Cpu className="h-5 w-5 text-purple-400" />;
    }
  };

  return (
    <div>
      <Topbar
        title="Décisions de l'Agent IA par Chauffeur"
        subtitle="Routage dynamique, profil de Qualité de Service (QoD CAMARA) et intégrité de flotte"
        onMenu={openMobileMenu}
      />

      <div className="p-6 space-y-6">
        {/* Header KPI cards */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <Card className="p-4 border-slate-800 bg-[#0f172a]">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-600/10 text-blue-400 ring-1 ring-blue-500/20">
                <Sparkles className="h-5 w-5 text-amber-400" />
              </div>
              <div>
                <p className="text-xs text-slate-400 uppercase font-semibold">Total Recommandations</p>
                <p className="text-2xl font-bold text-white">{decisions.length}</p>
              </div>
            </div>
          </Card>

          <Card className="p-4 border-slate-800 bg-[#0f172a]">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-cyan-600/10 text-cyan-400 ring-1 ring-cyan-500/20">
                <Zap className="h-5 w-5 text-cyan-400" />
              </div>
              <div>
                <p className="text-xs text-slate-400 uppercase font-semibold">Sessions QoD Allouées</p>
                <p className="text-2xl font-bold text-cyan-300">
                  {decisions.filter((d) => d.type === "QOD_BOOST").length}
                </p>
              </div>
            </div>
          </Card>

          <Card className="p-4 border-slate-800 bg-[#0f172a]">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-600/10 text-emerald-400 ring-1 ring-emerald-500/20">
                <ShieldCheck className="h-5 w-5 text-emerald-400" />
              </div>
              <div>
                <p className="text-xs text-slate-400 uppercase font-semibold">Fiabilité Globale IA</p>
                <p className="text-2xl font-bold text-emerald-400">98.9%</p>
              </div>
            </div>
          </Card>
        </div>

        {/* Filter Toolbar */}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2.5">
            {/* Filter by driver */}
            <select
              value={driverFilter}
              onChange={(e) => setDriverFilter(e.target.value)}
              className="rounded-xl border border-slate-800 bg-[#0f172a] px-3.5 py-2 text-xs font-semibold text-slate-200 outline-none transition focus:border-blue-500"
            >
              <option value="ALL">Tous les chauffeurs</option>
              {driverNames.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>

            {/* Filter by decision type */}
            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              className="rounded-xl border border-slate-800 bg-[#0f172a] px-3.5 py-2 text-xs font-semibold text-slate-200 outline-none transition focus:border-blue-500"
            >
              <option value="ALL">Tous les types d'action</option>
              <option value="REROUTE">Optimisation Itinéraire (Reroute)</option>
              <option value="QOD_BOOST">Boost Télématique (CAMARA QoD)</option>
              <option value="SIM_SWAP_VERIFY">Sécurité SIM & Terminaux</option>
              <option value="AUDIT_COMPLIANCE">Conformité Géofence</option>
            </select>
          </div>

          <Button variant="outline" size="sm" onClick={load} loading={loading}>
            <RefreshCw className="h-3.5 w-3.5 mr-1" /> Rafraîchir
          </Button>
        </div>

        {/* Decisions Cards List */}
        {loading ? (
          <div className="flex h-64 items-center justify-center">
            <Spinner />
          </div>
        ) : filtered.length === 0 ? (
          <Card className="p-8 border-slate-800 bg-[#0f172a]">
            <EmptyState
              icon={<Bot className="h-8 w-8 text-slate-500" />}
              title="Aucune décision d'agent pour ces critères"
              description="Sélectionnez un autre chauffeur ou réinitialisez les filtres."
            />
          </Card>
        ) : (
          <div className="space-y-4">
            {filtered.map((dec) => (
              <Card
                key={dec.id}
                className="p-5 border-slate-800 bg-[#0f172a] hover:border-slate-700 transition space-y-4 shadow-lg"
              >
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-800/80">
                  <div className="flex items-center gap-3">
                    <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-slate-900 border border-slate-700/60 shadow-inner">
                      {getTypeIcon(dec.type)}
                    </div>
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <h4 className="font-bold text-white text-sm sm:text-base">{dec.title}</h4>
                        <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-bold border ${getSeverityBadge(dec.severity)}`}>
                          {dec.severity}
                        </span>
                      </div>
                      <p className="text-xs text-slate-400 flex items-center gap-1.5 mt-0.5">
                        <Truck className="h-3.5 w-3.5 text-blue-400" /> Chauffeur : <strong className="text-slate-200">{dec.driver_name}</strong>
                        <span>•</span>
                        <span>Corridor : {dec.corridor}</span>
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-3 self-end sm:self-center">
                    <div className="text-right">
                      <span className="text-[11px] text-slate-400">Confiance IA</span>
                      <p className="font-mono text-xs font-bold text-emerald-400">{dec.confidence}%</p>
                    </div>
                    {dec.status === "EXECUTED" ? (
                      <span className="inline-flex items-center gap-1 rounded-lg bg-emerald-500/10 px-2.5 py-1 text-xs font-semibold text-emerald-400 border border-emerald-500/20">
                        <CheckCircle2 className="h-3.5 w-3.5" /> Appliquée
                      </span>
                    ) : (
                      <Button
                        variant="figma"
                        size="sm"
                        loading={actionId === dec.id}
                        onClick={() => applyDecision(dec.id, dec.title)}
                        className="text-xs"
                      >
                        Valider la recommandation
                      </Button>
                    )}
                  </div>
                </div>

                {/* Details Section */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                  <div className="rounded-xl border border-slate-800 bg-[#0a101d] p-3 space-y-1">
                    <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
                      Constat / Déclencheur télématique
                    </span>
                    <p className="text-slate-300">{dec.reason}</p>
                  </div>

                  <div className="rounded-xl border border-blue-500/20 bg-blue-950/20 p-3 space-y-1">
                    <span className="text-[11px] font-semibold text-blue-300 uppercase tracking-wider">
                      Recommandation de l'Agent IA
                    </span>
                    <p className="text-blue-200">{dec.recommendation}</p>
                  </div>
                </div>

                {/* Footer node info */}
                <div className="flex flex-wrap items-center justify-between gap-2 pt-1 text-[11px] text-slate-500">
                  <span>Réf fret : {dec.cargo_reference} • Nœud télécom : {dec.telecom_node}</span>
                  <span>Généré le {new Date(dec.timestamp).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })}</span>
                </div>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
