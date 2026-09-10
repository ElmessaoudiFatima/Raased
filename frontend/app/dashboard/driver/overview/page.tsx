"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  Boxes,
  CheckCircle2,
  Clock,
  Compass,
  Gauge,
  MapPin,
  Navigation,
  Radio,
  ShieldCheck,
  Thermometer,
  Truck,
  Zap,
} from "lucide-react";
import { Topbar } from "@/components/Topbar";
import { Badge, Button, Card, EmptyState, Spinner } from "@/components/ui";
import { useShell } from "@/components/ShellContext";
import { get } from "@/lib/api";
import { getUser } from "@/lib/auth";

interface DriverOverviewData {
  active_trips: number;
  delivered: number;
  open_alerts: number;
  current?: {
    cargo: {
      id: string;
      reference: string;
      type: string;
      criticality: string;
      origin: string;
      destination: string;
      deadline?: string | null;
      vehicle_registration?: string | null;
      device_id?: string | null;
    };
    position: {
      lat: number;
      lng: number;
      progress_pct: number;
      eta_minutes: number;
    } | null;
  } | null;
}

export default function DriverOverviewPage() {
  const { openMobileMenu } = useShell();
  const user = getUser();
  const [data, setData] = useState<DriverOverviewData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    get<{ stats: DriverOverviewData }>("/drivers/overview")
      .then((d) => setData(d.stats))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading || !data) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Spinner />
      </div>
    );
  }

  const current = data.current;
  const cargo = current?.cargo;
  const pos = current?.position;

  return (
    <div>
      <Topbar
        title={`Bonjour, ${user?.first_name || "Chauffeur"}`}
        subtitle="Tableau de bord de bordure et télématique convoi en temps réel"
        onMenu={openMobileMenu}
      />

      <div className="p-6 space-y-6">
        {/* KPI Grid */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Card className="p-5 border-slate-800 bg-[#0f172a]/90">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                  Mission en Cours
                </p>
                <p className="mt-2 text-2xl font-extrabold text-white">
                  {data.active_trips > 0 ? "1 Active" : "Aucune"}
                </p>
              </div>
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-blue-500/10 text-blue-400 ring-1 ring-blue-500/20">
                <Truck className="h-6 w-6" />
              </div>
            </div>
            <p className="mt-2 text-xs text-slate-400">
              {cargo ? `Réf : ${cargo.reference}` : "En attente d'attribution"}
            </p>
          </Card>

          <Card className="p-5 border-slate-800 bg-[#0f172a]/90">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                  Livraisons Terminées
                </p>
                <p className="mt-2 text-2xl font-extrabold text-emerald-400">{data.delivered}</p>
              </div>
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-emerald-500/10 text-emerald-400 ring-1 ring-emerald-500/20">
                <CheckCircle2 className="h-6 w-6" />
              </div>
            </div>
            <p className="mt-2 text-xs text-slate-400">Historique des missions réussies</p>
          </Card>

          <Card className="p-5 border-slate-800 bg-[#0f172a]/90">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                  Alertes Actives
                </p>
                <p className="mt-2 text-2xl font-extrabold text-amber-400">{data.open_alerts}</p>
              </div>
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-amber-500/10 text-amber-400 ring-1 ring-amber-500/20">
                <AlertTriangle className="h-6 w-6" />
              </div>
            </div>
            <p className="mt-2 text-xs text-slate-400">Surveillance route & fret</p>
          </Card>

          <Card className="p-5 border-slate-800 bg-[#0f172a]/90">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                  Qualité Réseau (QoD)
                </p>
                <p className="mt-2 text-2xl font-extrabold text-cyan-400">Optimum</p>
              </div>
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-cyan-500/10 text-cyan-400 ring-1 ring-cyan-500/20">
                <Zap className="h-6 w-6" />
              </div>
            </div>
            <p className="mt-2 text-xs text-slate-400">5G Standalone CAMARA connectée</p>
          </Card>
        </div>

        {/* Current Active Mission Banner */}
        {cargo ? (
          <Card className="p-6 border-blue-500/30 bg-gradient-to-br from-[#0f172a] via-[#111e38] to-[#0a101d] space-y-6 shadow-2xl">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-800/80">
              <div className="flex items-center gap-3">
                <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-blue-600 text-white shadow-lg shadow-blue-600/30">
                  <Compass className="h-6 w-6 animate-spin-slow" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="text-lg font-bold text-white">{cargo.reference}</h3>
                    <span className="rounded-full bg-blue-500/20 px-2.5 py-0.5 text-xs font-bold text-blue-300 border border-blue-500/30">
                      {cargo.type}
                    </span>
                  </div>
                  <p className="text-xs text-slate-400 mt-0.5">
                    Véhicule assigné : <strong className="text-slate-200">{cargo.vehicle_registration || "Camion Flotte"}</strong>
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-3">
                <Link
                  href="/dashboard/driver/map"
                  className="inline-flex items-center gap-2 rounded-xl bg-blue-600 hover:bg-blue-500 px-4 py-2.5 text-xs font-bold text-white shadow-lg shadow-blue-600/30 transition"
                >
                  <Navigation className="h-4 w-4" /> Ouvrir la navigation temps réel
                </Link>
              </div>
            </div>

            {/* Route & Progress Visualizer */}
            <div className="space-y-3">
              <div className="flex items-center justify-between text-xs text-slate-300 font-semibold">
                <span className="flex items-center gap-1.5 text-slate-200">
                  <MapPin className="h-4 w-4 text-emerald-400" /> Départ : {cargo.origin}
                </span>
                <span className="flex items-center gap-1.5 text-slate-200">
                  <MapPin className="h-4 w-4 text-red-400" /> Destination : {cargo.destination}
                </span>
              </div>

              <div className="relative h-3 w-full rounded-full bg-slate-800 overflow-hidden ring-1 ring-slate-700/50">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-blue-500 via-cyan-400 to-emerald-400 transition-all duration-500 shadow-sm"
                  style={{ width: `${Math.max(5, pos?.progress_pct || 42)}%` }}
                />
              </div>

              <div className="flex items-center justify-between text-xs text-slate-400">
                <span>Progression : <strong className="text-white">{pos?.progress_pct || 42}%</strong></span>
                <span>Temps estimé restant (ETA) : <strong className="text-cyan-400">{pos?.eta_minutes || 65} min</strong></span>
              </div>
            </div>

            {/* Live Telemetry Sensor Gauges */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-2">
              <div className="rounded-xl border border-slate-800/80 bg-[#0a101d] p-4 flex items-center gap-3">
                <Gauge className="h-8 w-8 text-blue-400 shrink-0" />
                <div>
                  <p className="text-[11px] text-slate-400 uppercase font-semibold">Vitesse Estimée</p>
                  <p className="text-xl font-mono font-bold text-white">82 km/h</p>
                </div>
              </div>

              <div className="rounded-xl border border-slate-800/80 bg-[#0a101d] p-4 flex items-center gap-3">
                <Thermometer className="h-8 w-8 text-cyan-400 shrink-0" />
                <div>
                  <p className="text-[11px] text-slate-400 uppercase font-semibold">Consigne Température</p>
                  <p className="text-xl font-mono font-bold text-emerald-400">+4.2 °C</p>
                </div>
              </div>

              <div className="rounded-xl border border-slate-800/80 bg-[#0a101d] p-4 flex items-center gap-3">
                <Clock className="h-8 w-8 text-purple-400 shrink-0" />
                <div>
                  <p className="text-[11px] text-slate-400 uppercase font-semibold">Deadline Contractuelle</p>
                  <p className="text-sm font-bold text-slate-200">
                    {cargo.deadline ? new Date(cargo.deadline).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" }) : "Ce soir"}
                  </p>
                </div>
              </div>
            </div>
          </Card>
        ) : (
          <Card className="p-8 border-slate-800 bg-[#0f172a]">
            <EmptyState
              icon={<Truck className="h-10 w-10 text-slate-500" />}
              title="Aucune mission en cours"
              description="Votre manager d'exploitation ne vous a pas encore assigné de nouveau convoi pour aujourd'hui."
            />
          </Card>
        )}

        {/* Quick Links Section */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Link
            href="/dashboard/driver/map"
            className="flex items-center justify-between rounded-2xl border border-slate-800 bg-[#0f172a] p-5 hover:border-blue-500/50 transition group"
          >
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-600/10 text-blue-400">
                <Navigation className="h-5 w-5" />
              </div>
              <div>
                <h4 className="font-semibold text-white group-hover:text-blue-400 transition">
                  Carte Google Maps en Direct
                </h4>
                <p className="text-xs text-slate-400">Suivre votre véhicule sur les corridors routiers</p>
              </div>
            </div>
            <ArrowRight className="h-4 w-4 text-slate-500 group-hover:translate-x-1 group-hover:text-blue-400 transition" />
          </Link>

          <Link
            href="/dashboard/driver/alerts"
            className="flex items-center justify-between rounded-2xl border border-slate-800 bg-[#0f172a] p-5 hover:border-amber-500/50 transition group"
          >
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-amber-600/10 text-amber-400">
                <AlertTriangle className="h-5 w-5" />
              </div>
              <div>
                <h4 className="font-semibold text-white group-hover:text-amber-400 transition">
                  Consignes & Décisions Agent IA
                </h4>
                <p className="text-xs text-slate-400">Alertes de trafic et propositions de déviations</p>
              </div>
            </div>
            <ArrowRight className="h-4 w-4 text-slate-500 group-hover:translate-x-1 group-hover:text-amber-400 transition" />
          </Link>
        </div>
      </div>
    </div>
  );
}
