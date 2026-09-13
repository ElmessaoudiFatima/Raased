"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  ArrowRight,
  Boxes,
  Building2,
  CheckCircle2,
  Clock,
  Globe,
  Radio,
  ShieldAlert,
  ShieldCheck,
  TrendingUp,
  Truck,
  Users,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Topbar } from "@/components/Topbar";
import { Card, Spinner } from "@/components/ui";
import { useShell } from "@/components/ShellContext";
import { get } from "@/lib/api";

interface AdminStats {
  pending: number;
  approved: number;
  rejected: number;
  total_organizations: number;
  managers: number;
  drivers: number;
  admins: number;
  total_users: number;
  cargos: number;
  in_transit: number;
  mena_distribution: { country: string; count: number }[];
  recent_audits: {
    id: string;
    action: string;
    actor_email: string;
    details: string;
    created_at: string;
  }[];
}

const PIE_COLORS = ["#10b981", "#f59e0b", "#ef4444"];

export default function AdminDashboardPage() {
  const { openMobileMenu } = useShell();
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    get<{ stats: AdminStats }>("/admin/stats")
      .then((d) => setStats(d.stats))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading || !stats) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Spinner />
      </div>
    );
  }

  const statusPieData = [
    { name: "Approved", value: stats.approved },
    { name: "Pending", value: stats.pending },
    { name: "Rejected", value: stats.rejected },
  ].filter((d) => d.value > 0);

  // Growth trend mock data based on live stats
  const trendData = [
    { month: "Jan", Registrations: Math.max(1, stats.total_organizations - 3), Cargo: Math.max(2, stats.cargos - 4) },
    { month: "Feb", Registrations: Math.max(1, stats.total_organizations - 2), Cargo: Math.max(3, stats.cargos - 2) },
    { month: "Mar", Registrations: stats.total_organizations, Cargo: stats.cargos },
  ];

  return (
    <div>
      <Topbar
        title="Super Administrator Dashboard"
        subtitle="Global supervision of organizations, MENA corridors, and operational security"
        onMenu={openMobileMenu}
      />

      <div className="p-6 space-y-6">
        {/* KPI Cards Grid */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Card className="p-5 border-slate-800 bg-[#0f172a]/90">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                  Active Companies
                </p>
                <p className="mt-2 text-3xl font-extrabold text-white">{stats.approved}</p>
              </div>
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-emerald-500/10 text-emerald-400 ring-1 ring-emerald-500/20">
                <Building2 className="h-6 w-6" />
              </div>
            </div>
            <div className="mt-3 flex items-center justify-between text-xs text-slate-400 pt-2 border-t border-slate-800">
              <span>Total registered: {stats.total_organizations}</span>
              <span className="text-emerald-400 font-semibold">{stats.pending} pending</span>
            </div>
          </Card>

          <Card className="p-5 border-slate-800 bg-[#0f172a]/90">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                  Pending Requests
                </p>
                <p className="mt-2 text-3xl font-extrabold text-amber-400">{stats.pending}</p>
              </div>
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-amber-500/10 text-amber-400 ring-1 ring-amber-500/20">
                <Clock className="h-6 w-6" />
              </div>
            </div>
            <div className="mt-3 flex items-center justify-between text-xs text-slate-400 pt-2 border-t border-slate-800">
              <Link href="/dashboard/admin/requests" className="text-blue-400 hover:underline flex items-center gap-1">
                Process requests <ArrowRight className="h-3 w-3" />
              </Link>
            </div>
          </Card>

          <Card className="p-5 border-slate-800 bg-[#0f172a]/90">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                  User Accounts
                </p>
                <p className="mt-2 text-3xl font-extrabold text-white">{stats.total_users}</p>
              </div>
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-blue-500/10 text-blue-400 ring-1 ring-blue-500/20">
                <Users className="h-6 w-6" />
              </div>
            </div>
            <div className="mt-3 flex items-center justify-between text-xs text-slate-400 pt-2 border-t border-slate-800">
              <span>{stats.managers} managers</span>
              <span className="text-cyan-400 font-semibold">{stats.drivers} drivers</span>
            </div>
          </Card>

          <Card className="p-5 border-slate-800 bg-[#0f172a]/90">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                  Cargo in Transit
                </p>
                <p className="mt-2 text-3xl font-extrabold text-cyan-400">{stats.in_transit}</p>
              </div>
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-cyan-500/10 text-cyan-400 ring-1 ring-cyan-500/20">
                <Truck className="h-6 w-6" />
              </div>
            </div>
            <div className="mt-3 flex items-center justify-between text-xs text-slate-400 pt-2 border-t border-slate-800">
              <span>Historical total: {stats.cargos}</span>
              <span className="text-emerald-400 font-semibold">Active QoD</span>
            </div>
          </Card>
        </div>

        {/* Charts Section */}
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          {/* Organization Status Pie Chart */}
          <Card className="p-6 border-slate-800 bg-[#0f172a]/90 space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-base font-bold text-white">Member Companies Status</h3>
                <p className="text-xs text-slate-400">Distribution of created accounts</p>
              </div>
              <Building2 className="h-5 w-5 text-blue-400" />
            </div>

            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={statusPieData}
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={90}
                    paddingAngle={6}
                    dataKey="value"
                    label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                  >
                    {statusPieData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={PIE_COLORS[index % PIE_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#0a101d",
                      borderColor: "#334155",
                      borderRadius: "0.75rem",
                      color: "#f8fafc",
                    }}
                  />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </Card>

          {/* MENA Countries Distribution Bar Chart */}
          <Card className="p-6 border-slate-800 bg-[#0f172a]/90 space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-base font-bold text-white">MENA Geographic Distribution</h3>
                <p className="text-xs text-slate-400">Logistics presence by country in the region</p>
              </div>
              <Globe className="h-5 w-5 text-cyan-400" />
            </div>

            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={stats.mena_distribution.length ? stats.mena_distribution : [{ country: "Morocco", count: 3 }]}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                  <XAxis dataKey="country" stroke="#64748b" fontSize={11} />
                  <YAxis stroke="#64748b" allowDecimals={false} fontSize={11} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#0a101d",
                      borderColor: "#334155",
                      borderRadius: "0.75rem",
                      color: "#f8fafc",
                    }}
                  />
                  <Bar dataKey="count" name="Companies" fill="#2563eb" radius={[6, 6, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Card>
        </div>

        {/* Growth Trends & Audit Log Snippet */}
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          {/* Trend */}
          <Card className="p-6 border-slate-800 bg-[#0f172a]/90 lg:col-span-2 space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-base font-bold text-white">Platform Growth & Activity</h3>
                <p className="text-xs text-slate-400">Quarterly evolution of registrations and monitored freight</p>
              </div>
              <TrendingUp className="h-5 w-5 text-emerald-400" />
            </div>

            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={trendData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                  <XAxis dataKey="month" stroke="#64748b" />
                  <YAxis stroke="#64748b" allowDecimals={false} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#0a101d",
                      borderColor: "#334155",
                      borderRadius: "0.75rem",
                      color: "#f8fafc",
                    }}
                  />
                  <Legend />
                  <Bar dataKey="Registrations" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="Cargo" fill="#06b6d4" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Card>

          {/* Live Audit Log preview */}
          <Card className="p-6 border-slate-800 bg-[#0f172a]/90 space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-base font-bold text-white">Recent Audits</h3>
                <p className="text-xs text-slate-400">Traceability & Security</p>
              </div>
              <ShieldCheck className="h-5 w-5 text-purple-400" />
            </div>

            <div className="space-y-3">
              {stats.recent_audits.length === 0 ? (
                <p className="text-xs text-slate-500">No recent audits recorded.</p>
              ) : (
                stats.recent_audits.map((a) => (
                  <div key={a.id} className="rounded-xl border border-slate-800/80 bg-slate-900/60 p-3 text-xs space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-blue-400">{a.action}</span>
                      <span className="text-[10px] text-slate-500">
                        {new Date(a.created_at).toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" })}
                      </span>
                    </div>
                    <p className="text-slate-300 truncate">{a.details}</p>
                    <p className="text-[10px] text-slate-500 truncate">{a.actor_email || "System"}</p>
                  </div>
                ))
              )}
            </div>

            <Link
              href="/dashboard/admin/audit"
              className="inline-flex items-center justify-center w-full rounded-xl border border-slate-800 bg-slate-800/60 py-2.5 text-xs font-semibold text-slate-300 hover:bg-slate-800 hover:text-white transition"
            >
              View full audit log <ArrowRight className="h-3 w-3 ml-1.5" />
            </Link>
          </Card>
        </div>
      </div>
    </div>
  );
}
