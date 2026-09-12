"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Boxes,
  Compass,
  Locate,
  RadioTower,
  RotateCw,
  Search,
  ShieldAlert,
  Target,
  Truck,
} from "lucide-react";
import MapView, { type LiveTrip } from "@/components/MapView";
import { Topbar } from "@/components/Topbar";
import { Badge, Spinner } from "@/components/ui";
import { useShell } from "@/components/ShellContext";
import { get } from "@/lib/api";

interface LivePayload {
  trips: LiveTrip[];
  corridors: { id: string; name: string; risk_level: string; origin?: string; destination?: string; points: [number, number][] }[];
  risk_zones: { id: string; name: string; type: string; risk_level: string; points: [number, number][] }[];
}

export default function LiveMapPage() {
  const { openMobileMenu } = useShell();
  const [data, setData] = useState<LivePayload>({ trips: [], corridors: [], risk_zones: [] });
  const [loading, setLoading] = useState(true);
  const [focus, setFocus] = useState<string | null>(null);
  const [lastRefresh, setLastRefresh] = useState<Date>(new Date());
  const [paused, setPaused] = useState(false);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const load = useCallback(async () => {
    try {
      let d: LivePayload;
      try {
        d = await get<LivePayload>("/managers/map/live");
      } catch {
        d = await get<LivePayload>("/map/live");
      }
      setData(d);
      setLastRefresh(new Date());
    } catch (err) {
      console.error("Erreur de chargement de la carte flotte:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    if (!timerRef.current) {
      timerRef.current = setInterval(() => {
        if (!paused) load();
      }, 5000);
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [load, paused]);

  return (
    <div className="flex h-screen flex-col bg-[#0a101d] overflow-hidden">
      <Topbar
        title="Carte Flotte & Corridors de l'Entreprise"
        subtitle="Géolocalisation en temps réel des cargaisons, suivi des trackers GPS et surveillance des corridors"
        onMenu={openMobileMenu}
      />
      <div className="relative flex-1 w-full min-h-0">
        <div className="absolute inset-0">
          {loading && data.trips.length === 0 ? (
            <div className="flex h-full w-full items-center justify-center bg-[#0a101d]">
              <div className="flex flex-col items-center gap-3">
                <Spinner />
                <p className="text-xs text-slate-400 font-medium">Chargement des positions GPS de la flotte…</p>
              </div>
            </div>
          ) : (
            <MapView
              trips={data.trips}
              corridors={data.corridors}
              riskZones={data.risk_zones}
              height="100%"
              fitTrip
              fitRef={focus}
              onTripFocus={setFocusDeep}
            />
          )}
        </div>

        {/* Floating Quick Stats & Refresh Controls */}
        <div className="absolute bottom-5 left-5 z-[500] flex flex-col gap-2 pointer-events-auto">
          <div className="flex items-center gap-2">
            <button
              onClick={() => {
                if (paused) load();
                setPaused((p) => !p);
              }}
              className="inline-flex items-center gap-2 rounded-xl bg-blue-600 hover:bg-blue-500 px-4 py-2.5 text-xs font-bold text-white shadow-xl shadow-blue-600/30 transition ring-1 ring-blue-400/30"
            >
              <RotateCw className={`h-4 w-4 ${paused ? "text-amber-300" : "animate-spin-slow"}`} />
              {paused ? "Reprendre le direct" : "Rafraîchir les positions"}
            </button>
            <button
              onClick={load}
              title="Forcer la mise à jour immédiate"
              className="rounded-xl border border-slate-700/80 bg-[#0f172a]/90 hover:bg-[#1e293b] p-2.5 text-slate-300 shadow-xl backdrop-blur transition"
            >
              <RotateCw className="h-4 w-4" />
            </button>
          </div>
          <div className="flex items-center gap-2 text-[11px] font-semibold text-slate-300">
            <span className="rounded-xl border border-slate-800 bg-[#0a101d]/90 px-3 py-1.5 shadow-xl backdrop-blur">
              🚚 {data.trips.length} cargaison(s) · {data.trips.filter(t => t.status === "IN_TRANSIT").length} en transit
            </span>
            <span className="rounded-xl border border-slate-800 bg-[#0a101d]/90 px-3 py-1.5 shadow-xl backdrop-blur text-slate-400">
              MAJ {lastRefresh.toLocaleTimeString("fr-FR")}
            </span>
          </div>
        </div>

        {/* Right Side Panel: Company Cargos & Live Fleet */}
        <LivePanel data={data} focus={focus} onFocus={setFocus} />
      </div>
    </div>
  );

  function setFocusDeep(ref: string) {
    setFocus(ref);
  }
}

function LivePanel({
  data,
  focus,
  onFocus,
}: {
  data: LivePayload;
  focus: string | null;
  onFocus: (ref: string) => void;
}) {
  const [open, setOpen] = useState(true);
  const [filter, setFilter] = useState<"ALL" | "IN_TRANSIT" | "PENDING">("ALL");
  const [search, setSearch] = useState("");

  const filteredTrips = useMemo(() => {
    return data.trips.filter((t) => {
      if (filter === "IN_TRANSIT" && t.status !== "IN_TRANSIT") return false;
      if (filter === "PENDING" && t.status !== "PENDING") return false;
      if (search.trim()) {
        const q = search.toLowerCase();
        const matchRef = t.reference?.toLowerCase().includes(q);
        const matchDest = t.destination?.toLowerCase().includes(q);
        const matchOrig = t.origin?.toLowerCase().includes(q);
        const matchType = t.type?.toLowerCase().includes(q);
        if (!matchRef && !matchDest && !matchOrig && !matchType) return false;
      }
      return true;
    });
  }, [data.trips, filter, search]);

  const movingCount = data.trips.filter((t) => t.status === "IN_TRANSIT" || t.position).length;

  return (
    <div className="absolute right-4 top-4 z-[500] w-84 max-w-[calc(100vw-2rem)] flex flex-col gap-2">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between rounded-2xl border border-slate-800 bg-[#0f172a]/95 px-4 py-3 text-white shadow-2xl backdrop-blur transition hover:border-blue-500/50"
      >
        <span className="flex items-center gap-2 text-sm font-bold">
          <RadioTower className="h-4 w-4 text-blue-400" /> Cargaisons de l'entreprise
        </span>
        <span className="flex items-center gap-1.5 rounded-full bg-blue-500/20 px-2.5 py-0.5 text-xs font-extrabold text-blue-300 border border-blue-500/30">
          <span className="h-2 w-2 rounded-full bg-emerald-400 animate-ping" />
          {movingCount} active(s)
        </span>
      </button>

      {open && (
        <div className="max-h-[75vh] flex flex-col rounded-2xl border border-slate-800 bg-[#0f172a]/95 backdrop-blur shadow-2xl overflow-hidden">
          {/* Filter Tabs & Search */}
          <div className="p-3 border-b border-slate-800/80 space-y-2.5 bg-slate-900/60">
            <div className="flex items-center gap-1 rounded-xl bg-slate-950/80 p-1 border border-slate-800 text-[11px] font-bold">
              <button
                type="button"
                onClick={() => setFilter("ALL")}
                className={`flex-1 py-1 text-center rounded-lg transition ${
                  filter === "ALL" ? "bg-blue-600 text-white shadow-sm" : "text-slate-400 hover:text-white"
                }`}
              >
                Tous ({data.trips.length})
              </button>
              <button
                type="button"
                onClick={() => setFilter("IN_TRANSIT")}
                className={`flex-1 py-1 text-center rounded-lg transition ${
                  filter === "IN_TRANSIT" ? "bg-blue-600 text-white shadow-sm" : "text-slate-400 hover:text-white"
                }`}
              >
                En transit ({data.trips.filter(t => t.status === "IN_TRANSIT").length})
              </button>
              <button
                type="button"
                onClick={() => setFilter("PENDING")}
                className={`flex-1 py-1 text-center rounded-lg transition ${
                  filter === "PENDING" ? "bg-blue-600 text-white shadow-sm" : "text-slate-400 hover:text-white"
                }`}
              >
                En attente ({data.trips.filter(t => t.status === "PENDING").length})
              </button>
            </div>

            <div className="relative">
              <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-slate-500" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Rechercher cargaison, ville, type…"
                className="w-full rounded-xl border border-slate-800 bg-slate-950/80 pl-8 pr-3 py-1.5 text-xs text-white placeholder:text-slate-500 focus:border-blue-500 focus:outline-none"
              />
            </div>
          </div>

          {/* List of Cargos */}
          <div className="overflow-y-auto divide-y divide-slate-800/60 p-1.5 max-h-[55vh]">
            {filteredTrips.length === 0 ? (
              <div className="px-4 py-8 text-center text-xs text-slate-500">
                <Truck className="h-8 w-8 mx-auto mb-2 text-slate-600 opacity-60" />
                Aucune cargaison trouvée pour ce filtre.
              </div>
            ) : (
              filteredTrips.map((t) => {
                const isSelected = focus === t.reference;
                return (
                  <button
                    key={t.cargo_id}
                    onClick={() => onFocus(t.reference)}
                    className={`flex w-full items-start gap-3 rounded-xl p-2.5 text-left transition hover:bg-slate-800/60 ${
                      isSelected ? "bg-blue-600/15 border border-blue-500/50 shadow-md" : ""
                    }`}
                  >
                    <div
                      className={`mt-1 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl text-xs font-bold text-white shadow ${
                        t.criticality === "CRITICAL"
                          ? "bg-red-600"
                          : t.criticality === "HIGH"
                          ? "bg-amber-600"
                          : t.criticality === "MEDIUM"
                          ? "bg-blue-600"
                          : "bg-emerald-600"
                      }`}
                    >
                      <Truck className="h-4 w-4" />
                    </div>
                    <div className="min-w-0 flex-1 space-y-1">
                      <div className="flex items-center justify-between gap-1">
                        <p className="truncate text-xs font-extrabold text-white">{t.reference}</p>
                        <span
                          className={`text-[10px] font-extrabold px-2 py-0.5 rounded-full border ${
                            t.status === "IN_TRANSIT"
                              ? "bg-cyan-500/20 text-cyan-300 border-cyan-500/30"
                              : t.status === "DELIVERED"
                              ? "bg-emerald-500/20 text-emerald-300 border-emerald-500/30"
                              : "bg-slate-800 text-slate-300 border-slate-700"
                          }`}
                        >
                          {t.status === "IN_TRANSIT" ? "EN TRANSIT" : t.status === "DELIVERED" ? "LIVRÉ" : "EN ATTENTE"}
                        </span>
                      </div>

                      <p className="flex items-center gap-1 truncate text-[11px] text-slate-300 font-medium">
                        <Target className="h-3 w-3 shrink-0 text-blue-400" /> {t.origin} ➔ {t.destination}
                      </p>

                      <div className="flex items-center justify-between text-[11px] text-slate-400">
                        <span className="flex items-center gap-1 truncate max-w-[140px]">
                          <Boxes className="h-3 w-3 text-slate-500 shrink-0" /> {t.type}
                        </span>
                        {t.vehicle_registration && (
                          <span className="text-[10px] bg-slate-800/80 px-1.5 py-0.5 rounded text-slate-300 font-mono">
                            {t.vehicle_registration}
                          </span>
                        )}
                      </div>

                      {t.position && (
                        <div className="pt-1.5 space-y-1">
                          <div className="flex items-center justify-between text-[10px] font-semibold">
                            <span className="flex items-center gap-1 text-cyan-400">
                              <Locate className="h-2.5 w-2.5 animate-pulse" /> {t.position.progress_pct}%
                            </span>
                            <span className="text-slate-400 font-medium">
                              ETA : ~{t.position.eta_minutes} min
                            </span>
                          </div>
                          {/* Mini progress bar */}
                          <div className="h-1.5 w-full rounded-full bg-slate-800 overflow-hidden">
                            <div
                              className="h-full rounded-full bg-gradient-to-r from-blue-500 to-cyan-400 transition-all duration-500"
                              style={{ width: `${Math.max(5, t.position.progress_pct)}%` }}
                            />
                          </div>
                        </div>
                      )}
                    </div>
                  </button>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
}