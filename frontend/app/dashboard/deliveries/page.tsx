"use client";

import { useEffect, useState } from "react";
import { History, Package, Truck } from "lucide-react";
import { Topbar } from "@/components/Topbar";
import { Badge, Card, EmptyState, Spinner } from "@/components/ui";
import { useShell } from "@/components/ShellContext";
import { get } from "@/lib/api";

interface TripOverview {
  active_trips: number;
  delivered: number;
  open_alerts: number;
  current?: {
    cargo: {
      reference: string;
      type: string;
      criticality: string;
      origin: string;
      destination: string;
      vehicle_registration?: string | null;
    };
    position: { progress_pct: number; eta_minutes: number } | null;
  } | null;
}

interface HistoryCargo {
  id: string;
  reference: string;
  type: string;
  criticality: string;
  status: string;
  origin: string;
  destination: string;
}

export default function DeliveriesPage() {
  const { openMobileMenu } = useShell();
  const [overview, setOverview] = useState<TripOverview | null>(null);
  const [history, setHistory] = useState<HistoryCargo[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    get<{ stats: TripOverview }>("/drivers/overview")
      .then((d) => setOverview(d.stats))
      .catch(() => {});
    get<{ cargos: HistoryCargo[] }>("/drivers/history")
      .then((d) => setHistory(d.cargos))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <Topbar title="My Deliveries" subtitle="Driver view — your convoys" onMenu={openMobileMenu} />
      <div className="p-6">
        {loading ? (
          <div className="flex h-40 items-center justify-center">
            <Spinner className="h-7 w-7 text-raased-teal" />
          </div>
        ) : (
          <>
            {overview?.current && (
              <Card className="mb-6 border-l-4 border-l-raased-teal p-5">
                <div className="flex flex-wrap items-center justify-between gap-4">
                  <div className="flex items-center gap-4">
                    <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-teal-50 text-raased-teal">
                      <Truck className="h-6 w-6" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <p className="font-bold text-raased-navy">
                          {overview.current.cargo.reference}
                        </p>
                        <Badge value={overview.current.cargo.criticality} />
                      </div>
                      <p className="text-sm text-slate-500">
                        {overview.current.cargo.origin} → {overview.current.cargo.destination}
                      </p>
                      {overview.current.cargo.vehicle_registration && (
                        <p className="text-xs text-slate-400">
                          Vehicle: {overview.current.cargo.vehicle_registration} · {overview.current.cargo.type.replace(/_/g, " ")}
                        </p>
                      )}
                    </div>
                  </div>
                  {overview.current.position && (
                    <div className="text-right">
                      <p className="text-2xl font-extrabold text-raased-teal">
                        {overview.current.position.progress_pct}%
                      </p>
                      <p className="text-xs text-slate-400">of journey · ETA ~{overview.current.position.eta_minutes} min</p>
                    </div>
                  )}
                </div>
              </Card>
            )}

            {!overview?.current && (
              <EmptyState
                icon={<Package className="h-8 w-8" />}
                title="No ongoing convoy"
                description="Waiting for an assignment by your manager."
              />
            )}

            {history.length > 0 && (
              <Card className="mt-6 overflow-hidden">
                <div className="flex items-center gap-2 border-b border-slate-100 px-5 py-4">
                  <History className="h-4 w-4 text-slate-400" />
                  <h3 className="font-bold text-raased-navy">Completed deliveries</h3>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm">
                    <thead>
                      <tr className="border-b border-slate-100 bg-slate-50/70 text-xs uppercase tracking-wide text-slate-500">
                        <th className="px-5 py-3 font-semibold">Reference</th>
                        <th className="px-5 py-3 font-semibold">Route</th>
                        <th className="px-5 py-3 font-semibold">Type</th>
                        <th className="px-5 py-3 font-semibold">Criticality</th>
                        <th className="px-5 py-3 font-semibold">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {history.map((c) => (
                        <tr key={c.id} className="hover:bg-slate-50/60">
                          <td className="px-5 py-3.5 font-semibold text-raased-navy">{c.reference}</td>
                          <td className="px-5 py-3.5 text-slate-500">
                            {c.origin} → {c.destination}
                          </td>
                          <td className="px-5 py-3.5 text-slate-500">{c.type.replace(/_/g, " ")}</td>
                          <td className="px-5 py-3.5">
                            <Badge value={c.criticality} />
                          </td>
                          <td className="px-5 py-3.5">
                            <Badge value={c.status} />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>
            )}
          </>
        )}
      </div>
    </div>
  );
}