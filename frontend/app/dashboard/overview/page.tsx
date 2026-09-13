"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  ArrowRight,
  Boxes,
  Radio,
  Truck,
} from "lucide-react";
import {
  Bar,
  BarChart,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Topbar } from "@/components/Topbar";
import { StatsCard } from "@/components/StatsCard";
import { Card, Badge, Spinner } from "@/components/ui";
import { useShell } from "@/components/ShellContext";
import { get } from "@/lib/api";

interface OverviewStats {
  drivers: number;
  active_drivers: number;
  invited_drivers: number;
  in_transit: number;
  delivered: number;
  trackers: number;
  active_trackers: number;
  open_alerts: number;
  co_managers: number;
}

export default function ManagerOverview() {
  const { openMobileMenu } = useShell();
  const [stats, setStats] = useState<OverviewStats | null>(null);
  const [cargos, setCargos] = useState<{ reference: string; status: string }[]>([]);
  const [alerts, setAlerts] = useState<
    { id: string; severity: string; title: string; message: string; status: string }[]
  >([]);
  const [orgName, setOrgName] = useState("");

  useEffect(() => {
    get<{ stats: OverviewStats }>("/managers/overview")
      .then((d) => setStats(d.stats))
      .catch(() => {});
    get<any>("/managers/cargos")
      .then((d) => setCargos(Array.isArray(d) ? d : (d?.cargos ?? [])))
      .catch(() => setCargos([]));
    get<{ alerts: { id: string; severity: string; title: string; message: string; status: string }[] }>(
      "/managers/alerts"
    )
      .then((d) => setAlerts((Array.isArray(d) ? d : (d?.alerts ?? [])).slice(0, 5)))
      .catch(() => setAlerts([]));
    get<{ organization: { name: string } | null }>("/managers/me")
      .then((d) => d?.organization && setOrgName(d.organization.name))
      .catch(() => {});
  }, []);

  const statusCounts = (() => {
    const map: Record<string, number> = {};
    for (const c of (cargos || [])) map[c.status] = (map[c.status] || 0) + 1;
    return Object.entries(map).map(([name, value]) => ({ name, value }));
  })();

  const statusColors: Record<string, string> = {
    IN_TRANSIT: "#0d7377",
    DELIVERED: "#22c55e",
    PENDING: "#cbd5e1",
    CANCELLED: "#ef4444",
  };

  return (
    <div>
      <Topbar
        title="Dashboard"
        subtitle={orgName ? `${orgName} — Manager View` : "Manager View"}
        onMenu={openMobileMenu}
      />
      <div className="p-6">
        {!stats ? (
          <div className="flex h-40 items-center justify-center">
            <Spinner className="h-7 w-7 text-raased-teal" />
          </div>
        ) : (
          <>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <StatsCard
                icon={<Truck className="h-5 w-5" />}
                label="Drivers"
                value={stats.drivers}
                accent="teal"
                sub={`${stats.active_drivers} active · ${stats.invited_drivers} invited`}
              />
              <StatsCard
                icon={<Boxes className="h-5 w-5" />}
                label="Cargo in Transit"
                value={stats.in_transit}
                accent="navy"
                sub={`${stats.delivered} delivered`}
              />
              <StatsCard
                icon={<Radio className="h-5 w-5" />}
                label="GPS Trackers"
                value={stats.trackers}
                accent="emerald"
                sub={`${stats.active_trackers} active`}
              />
              <StatsCard
                icon={<AlertTriangle className="h-5 w-5" />}
                label="Open Alerts"
                value={stats.open_alerts}
                accent={stats.open_alerts > 0 ? "red" : "emerald"}
              />
            </div>

            <div className="mt-6 grid grid-cols-1 gap-6 xl:grid-cols-3">
              <Card className="p-5 xl:col-span-2">
                <div className="mb-4 flex items-center justify-between">
                  <h3 className="font-bold text-raased-navy">Cargo Shipments by Status</h3>
                  <Link
                    href="/dashboard/cargos"
                    className="inline-flex items-center gap-1 text-sm font-semibold text-raased-teal hover:text-raased-navy"
                  >
                    View all <ArrowRight className="h-4 w-4" />
                  </Link>
                </div>
                {statusCounts.length ? (
                  <div className="h-64">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={statusCounts}>
                        <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                        <YAxis allowDecimals={false} tick={{ fontSize: 12 }} width={30} />
                        <Tooltip />
                        <Bar dataKey="value" radius={[8, 8, 0, 0]} fill="#0d7377">
                          {statusCounts.map((s) => (
                            <Cell key={s.name} fill={statusColors[s.name] || "#0d7377"} />
                          ))}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                ) : (
                  <p className="py-10 text-center text-sm text-slate-400">No shipments found.</p>
                )}
              </Card>

              <Card className="p-5">
                <h3 className="mb-4 font-bold text-raased-navy">Fleet Resource Distribution</h3>
                <div className="h-52">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={statusCounts}
                        dataKey="value"
                        nameKey="name"
                        innerRadius={50}
                        outerRadius={80}
                        paddingAngle={3}
                      >
                        {statusCounts.map((s) => (
                          <Cell key={s.name} fill={statusColors[s.name] || "#0d7377"} />
                        ))}
                      </Pie>
                      <Tooltip />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
                <div className="mt-2 flex flex-wrap gap-2">
                  {statusCounts.map((s) => (
                    <span key={s.name} className="badge bg-slate-100 text-slate-600">
                      {s.name.replace(/_/g, " ")} · {s.value}
                    </span>
                  ))}
                  {!statusCounts.length && (
                    <span className="text-xs text-slate-400">No data</span>
                  )}
                </div>
              </Card>
            </div>

            {alerts.length > 0 && (
              <Card className="mt-6 p-5">
                <div className="mb-4 flex items-center justify-between">
                  <h3 className="font-bold text-raased-navy">Recent Alerts</h3>
                  <Link
                    href="/dashboard/alerts"
                    className="inline-flex items-center gap-1 text-sm font-semibold text-raased-teal hover:text-raased-navy"
                  >
                    View all <ArrowRight className="h-4 w-4" />
                  </Link>
                </div>
                <div className="divide-y divide-slate-100">
                  {alerts.map((a) => (
                    <div key={a.id} className="flex items-center gap-3 py-3">
                      <Badge value={a.severity} />
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-semibold text-slate-700">{a.title}</p>
                        <p className="truncate text-xs text-slate-400">{a.message}</p>
                      </div>
                      <Badge value={a.status} />
                    </div>
                  ))}
                </div>
              </Card>
            )}
          </>
        )}
      </div>
    </div>
  );
}