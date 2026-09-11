"use client";

import { useEffect, useState } from "react";
import {
  Activity,
  Calendar,
  Clock,
  Filter,
  RefreshCw,
  Search,
  ShieldCheck,
  Terminal,
} from "lucide-react";
import { Topbar } from "@/components/Topbar";
import { Badge, Button, Card, EmptyState, Spinner } from "@/components/ui";
import { useShell } from "@/components/ShellContext";
import { useToast } from "@/components/Toasts";
import { get } from "@/lib/api";

interface AuditLogItem {
  id: string;
  actor_id?: string | null;
  actor_email?: string | null;
  action: string;
  target_type?: string | null;
  target_id?: string | null;
  ip_address?: string | null;
  details: string;
  created_at: string;
}

export default function AdminAuditPage() {
  const { openMobileMenu } = useShell();
  const { notify } = useToast();

  const [logs, setLogs] = useState<AuditLogItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [actionFilter, setActionFilter] = useState("ALL");

  const load = () => {
    setLoading(true);
    get<{ logs: AuditLogItem[] }>("/admin/audit")
      .then((d) => setLogs(d.logs))
      .catch(() => notify("Impossible de charger les journaux d'audit.", "error"))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const filtered = logs.filter((l) => {
    const q = search.toLowerCase();
    const matchesSearch =
      l.action.toLowerCase().includes(q) ||
      (l.actor_email || "").toLowerCase().includes(q) ||
      (l.details || "").toLowerCase().includes(q) ||
      (l.ip_address || "").includes(q);

    const matchesAction = actionFilter === "ALL" || l.action.startsWith(actionFilter);

    return matchesSearch && matchesAction;
  });

  const getActionBadge = (action: string) => {
    if (action.includes("APPROVED") || action.includes("LOGIN")) {
      return "bg-emerald-500/20 text-emerald-300 border-emerald-500/30";
    }
    if (action.includes("REJECT") || action.includes("DELETE")) {
      return "bg-red-500/20 text-red-300 border-red-500/30";
    }
    if (action.includes("CAMARA") || action.includes("SIM")) {
      return "bg-cyan-500/20 text-cyan-300 border-cyan-500/30";
    }
    return "bg-blue-500/20 text-blue-300 border-blue-500/30";
  };

  return (
    <div>
      <Topbar
        title="Journal d'Audit et Sécurité"
        subtitle="Traçabilité immuable, événements CAMARA, authentification et conformité opérationnelle"
        onMenu={openMobileMenu}
      />

      <div className="p-6 space-y-6">
        {/* Controls */}
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
            <input
              type="text"
              placeholder="Filtrer par acteur, action, IP ou mot-clé..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full rounded-xl border border-slate-800 bg-[#0f172a] pl-10 pr-4 py-2.5 text-sm text-slate-100 placeholder:text-slate-500 outline-none transition focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
            />
          </div>

          <div className="flex items-center gap-2.5">
            <select
              value={actionFilter}
              onChange={(e) => setActionFilter(e.target.value)}
              className="rounded-xl border border-slate-800 bg-[#0f172a] px-3 py-2 text-xs font-semibold text-slate-300 outline-none transition focus:border-blue-500"
            >
              <option value="ALL">Toutes les actions</option>
              <option value="AUTH">Authentification (AUTH)</option>
              <option value="ORG">Organisations (ORG)</option>
              <option value="USER">Comptes Utilisateurs (USER)</option>
              <option value="CAMARA">Télécom & CAMARA</option>
              <option value="SIM">SIM Swap & Intégrité</option>
            </select>

            <Button variant="outline" size="sm" onClick={load} loading={loading}>
              <RefreshCw className="h-3.5 w-3.5 mr-1" /> Actualiser
            </Button>
          </div>
        </div>

        {/* Audit Log Table */}
        <Card className="overflow-hidden border-slate-800 bg-[#0f172a]">
          {loading ? (
            <div className="flex h-64 items-center justify-center">
              <Spinner />
            </div>
          ) : filtered.length === 0 ? (
            <EmptyState
              icon={<ShieldCheck className="h-8 w-8 text-slate-500" />}
              title="Aucun journal d'audit correspondant"
              description="Aucun événement ne correspond à vos filtres actuels."
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm text-slate-300">
                <thead className="border-b border-slate-800 bg-slate-900/60 text-xs font-semibold uppercase tracking-wider text-slate-400">
                  <tr>
                    <th className="px-5 py-3.5">Horodatage (UTC)</th>
                    <th className="px-4 py-3.5">Action</th>
                    <th className="px-4 py-3.5">Acteur</th>
                    <th className="px-4 py-3.5">Cible</th>
                    <th className="px-4 py-3.5">Adresse IP</th>
                    <th className="px-5 py-3.5">Détails de l'événement</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/80 font-mono text-xs">
                  {filtered.map((log) => (
                    <tr key={log.id} className="hover:bg-slate-800/40 transition">
                      <td className="px-5 py-3.5 text-slate-400 whitespace-nowrap">
                        {new Date(log.created_at).toLocaleString("fr-FR", {
                          year: "numeric",
                          month: "2-digit",
                          day: "2-digit",
                          hour: "2-digit",
                          minute: "2-digit",
                          second: "2-digit",
                        })}
                      </td>

                      <td className="px-4 py-3.5 whitespace-nowrap">
                        <span
                          className={`inline-flex items-center gap-1 rounded px-2 py-0.5 text-[11px] font-bold border ${getActionBadge(
                            log.action
                          )}`}
                        >
                          {log.action}
                        </span>
                      </td>

                      <td className="px-4 py-3.5 text-slate-300 whitespace-nowrap">
                        {log.actor_email || "Système interne"}
                      </td>

                      <td className="px-4 py-3.5 text-slate-400 whitespace-nowrap">
                        {log.target_type ? `${log.target_type}` : "—"}
                      </td>

                      <td className="px-4 py-3.5 text-cyan-400 whitespace-nowrap">
                        {log.ip_address || "127.0.0.1"}
                      </td>

                      <td className="px-5 py-3.5 font-sans text-xs text-slate-200 max-w-md">
                        {log.details}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
