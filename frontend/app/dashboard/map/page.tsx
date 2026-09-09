"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  Boxes,
  Clock,
  Locate,
  RadioTower,
  RotateCw,
  Target,
} from "lucide-react";
import MapView, { type LiveTrip } from "@/components/MapView";
import { Topbar } from "@/components/Topbar";
import { Badge, Spinner } from "@/components/ui";
import { useShell } from "@/components/ShellContext";
import { get } from "@/lib/api";

interface LivePayload {
  trips: LiveTrip[];
  corridors: { id: string; name: string; risk_level: string; points: [number, number][] }[];
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
      const d = await get<LivePayload>("/map/live");
      setData(d);
      setLastRefresh(new Date());
    } catch {
      /* garde le dernier état */
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
    <div className="flex h-screen flex-col bg-[#0a101d]">
      <Topbar
        title="Carte Flotte & Corridors MENA"
        subtitle="Géolocalisation des convois, corridors autoroutiers et surveillance des zones à risque"
        onMenu={openMobileMenu}
      />
      <div className="relative flex-1">
        {loading && data.trips.length === 0 ? (
          <div className="flex h-full items-center justify-center bg-[#0a101d]">
            <Spinner />
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

        <div className="absolute bottom-5 left-5 z-[500] flex flex-col gap-2.5">
          <button
            onClick={() => {
              setPaused((p) => !p);
            }}
            className="inline-flex items-center gap-2 rounded-xl bg-blue-600 hover:bg-blue-500 px-4 py-2.5 text-xs font-bold text-white shadow-xl shadow-blue-600/30 transition ring-1 ring-blue-400/30"
          >
            <RotateCw className={`h-4 w-4 ${paused ? "text-amber-300" : ""}`} />
            {paused ? "Reprendre le direct" : "Rafraîchir la position"}
          </button>
          <p className="rounded-xl border border-slate-800 bg-[#0a101d]/90 px-3.5 py-2 text-xs font-semibold text-slate-300 shadow-xl backdrop-blur">
            {data.trips.length} convoyeur(s) en transit · MAJ {lastRefresh.toLocaleTimeString("fr-FR")}
          </p>
        </div>

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
  const moving = data.trips.filter((t) => t.position);

  return (
    <div className="absolute right-4 top-4 z-[500] w-80 max-w-[calc(100vw-2rem)]">
      <button
        onClick={() => setOpen((o) => !o)}
        className="mb-2 flex w-full items-center justify-between rounded-xl border border-slate-800 bg-[#0f172a]/95 px-4 py-3 text-white shadow-2xl backdrop-blur transition hover:border-blue-500/50"
      >
        <span className="flex items-center gap-2 text-sm font-bold">
          <RadioTower className="h-4 w-4 text-blue-400" /> Flotte en mouvement
        </span>
        <span className="rounded-full bg-blue-500/20 px-2 py-0.5 text-xs font-extrabold text-blue-300 border border-blue-500/30">
          {moving.length}
        </span>
      </button>

      {open && (
        <div className="max-h-[65vh] overflow-y-auto rounded-2xl border border-slate-800 bg-[#0f172a]/95 backdrop-blur shadow-2xl space-y-1 p-1.5">
          {moving.length === 0 && (
            <p className="px-4 py-8 text-center text-xs text-slate-500">
              Aucun convoi en mouvement actuellement.
            </p>
          )}
          <div className="divide-y divide-slate-800/80">
            {moving.map((t) => (
              <button
                key={t.cargo_id}
                onClick={() => onFocus(t.reference)}
                className={`flex w-full items-start gap-3 rounded-xl p-3 text-left transition hover:bg-slate-800/60 ${
                  focus === t.reference ? "bg-blue-600/15 border border-blue-500/40" : ""
                }`}
              >
                <div
                  className={`mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl text-xs font-bold text-white shadow ${
                    t.criticality === "CRITICAL"
                      ? "bg-red-600"
                      : t.criticality === "HIGH"
                      ? "bg-amber-600"
                      : t.criticality === "MEDIUM"
                      ? "bg-blue-600"
                      : "bg-emerald-600"
                  }`}
                >
                  {t.vehicle_registration?.slice(-2) || "R"}
                </div>
                <div className="min-w-0 flex-1 space-y-1">
                  <div className="flex items-center justify-between">
                    <p className="truncate text-xs font-bold text-white">{t.reference}</p>
                    <Badge variant={t.criticality === "CRITICAL" ? "danger" : t.criticality === "HIGH" ? "warning" : "success"}>
                      {t.criticality}
                    </Badge>
                  </div>
                  <p className="flex items-center gap-1 truncate text-[11px] text-slate-400">
                    <Target className="h-3 w-3 shrink-0 text-blue-400" /> {t.origin} → {t.destination}
                  </p>
                  <p className="flex items-center gap-2 text-[11px] text-slate-500">
                    <span className="flex items-center gap-1">
                      <Boxes className="h-3 w-3" /> {t.type}
                    </span>
                    {t.driver && <span>· Chauffeur : {t.driver}</span>}
                  </p>
                  {t.position && (
                    <p className="flex items-center justify-between text-[11px] font-semibold text-cyan-400 pt-1">
                      <span className="flex items-center gap-1">
                        <Locate className="h-3 w-3" /> {t.position.progress_pct}%
                      </span>
                      <span className="text-slate-400">
                        ETA : ~{t.position.eta_minutes} min
                      </span>
                    </p>
                  )}
                </div>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}