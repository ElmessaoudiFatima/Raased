"use client";

import { useEffect, useState } from "react";
import {
  Building2,
  CheckCircle2,
  Filter,
  Mail,
  MoreVertical,
  Phone,
  Power,
  RefreshCw,
  Search,
  Shield,
  Trash2,
  UserCheck,
  UserX,
  Users,
} from "lucide-react";
import { Topbar } from "@/components/Topbar";
import { Badge, Button, Card, EmptyState, Modal, Spinner } from "@/components/ui";
import { useShell } from "@/components/ShellContext";
import { useToast } from "@/components/Toasts";
import { del, get, patch } from "@/lib/api";
import { getUser } from "@/lib/auth";

interface AdminUser {
  id: string;
  first_name: string;
  last_name: string;
  email: string;
  phone?: string | null;
  job_title?: string | null;
  role: string;
  avatar_url?: string | null;
  account_status: string;
  is_active: boolean;
  email_verified: boolean;
  created_at: string;
  organization?: {
    id: string;
    name: string;
    city: string;
    country: string;
    status: string;
  } | null;
}

export default function AdminUsersPage() {
  const { openMobileMenu } = useShell();
  const { notify } = useToast();
  const currentUser = getUser();

  const [users, setUsers] = useState<AdminUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [roleFilter, setRoleFilter] = useState("ALL");
  const [statusFilter, setStatusFilter] = useState("ALL");

  const [deleteTarget, setDeleteTarget] = useState<AdminUser | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [actionId, setActionId] = useState<string | null>(null);

  const load = () => {
    setLoading(true);
    get<{ users: AdminUser[] }>("/admin/users")
      .then((d) => setUsers(d.users))
      .catch(() => notify("Impossible de charger les utilisateurs.", "error"))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const toggleStatus = async (user: AdminUser) => {
    setActionId(user.id);
    const action = user.is_active ? "disable" : "enable";
    try {
      await patch(`/admin/users/${user.id}/status`, { action });
      notify(action === "enable" ? "Compte réactivé." : "Compte désactivé.");
      load();
    } catch (err) {
      notify(err instanceof Error ? err.message : "Erreur de mise à jour.", "error");
    } finally {
      setActionId(null);
    }
  };

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await del(`/admin/users/${deleteTarget.id}`);
      notify(`Compte de ${deleteTarget.first_name} ${deleteTarget.last_name} supprimé.`);
      setDeleteTarget(null);
      load();
    } catch (err) {
      notify(err instanceof Error ? err.message : "Impossible de supprimer.", "error");
    } finally {
      setDeleting(false);
    }
  };

  const filtered = users.filter((u) => {
    const q = search.toLowerCase();
    const matchesSearch =
      u.first_name.toLowerCase().includes(q) ||
      u.last_name.toLowerCase().includes(q) ||
      u.email.toLowerCase().includes(q) ||
      (u.organization?.name || "").toLowerCase().includes(q) ||
      (u.phone || "").includes(q);

    const matchesRole = roleFilter === "ALL" || u.role === roleFilter;
    const matchesStatus =
      statusFilter === "ALL" ||
      (statusFilter === "ACTIVE" && u.is_active && u.account_status === "ACTIVE") ||
      (statusFilter === "DISABLED" && (!u.is_active || u.account_status === "DISABLED")) ||
      (statusFilter === "INVITED" && u.account_status === "INVITED");

    return matchesSearch && matchesRole && matchesStatus;
  });

  return (
    <div>
      <Topbar
        title="Gestion des Comptes Utilisateurs"
        subtitle="Contrôle d'accès, activation/désactivation et administration des rôles"
        onMenu={openMobileMenu}
      />

      <div className="p-6 space-y-6">
        {/* Search & Filter Bar */}
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
            <input
              type="text"
              placeholder="Rechercher par nom, email, entreprise..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full rounded-xl border border-slate-800 bg-[#0f172a] pl-10 pr-4 py-2.5 text-sm text-slate-100 placeholder:text-slate-500 outline-none transition focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
            />
          </div>

          <div className="flex flex-wrap items-center gap-2.5">
            {/* Role filter */}
            <select
              value={roleFilter}
              onChange={(e) => setRoleFilter(e.target.value)}
              className="rounded-xl border border-slate-800 bg-[#0f172a] px-3 py-2 text-xs font-semibold text-slate-300 outline-none transition focus:border-blue-500"
            >
              <option value="ALL">Tous les rôles</option>
              <option value="ADMIN">ADMIN</option>
              <option value="MANAGER">MANAGER</option>
              <option value="DRIVER">DRIVER</option>
            </select>

            {/* Status filter */}
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="rounded-xl border border-slate-800 bg-[#0f172a] px-3 py-2 text-xs font-semibold text-slate-300 outline-none transition focus:border-blue-500"
            >
              <option value="ALL">Tous les statuts</option>
              <option value="ACTIVE">Actif</option>
              <option value="DISABLED">Désactivé</option>
              <option value="INVITED">Invité</option>
            </select>

            <Button variant="outline" size="sm" onClick={load} loading={loading}>
              <RefreshCw className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>

        {/* Users Table */}
        <Card className="overflow-hidden border-slate-800 bg-[#0f172a]">
          {loading ? (
            <div className="flex h-64 items-center justify-center">
              <Spinner />
            </div>
          ) : filtered.length === 0 ? (
            <EmptyState
              icon={<Users className="h-8 w-8" />}
              title="Aucun utilisateur trouvé"
              description="Modifiez vos critères de recherche ou vos filtres."
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm text-slate-300">
                <thead className="border-b border-slate-800 bg-slate-900/60 text-xs font-semibold uppercase tracking-wider text-slate-400">
                  <tr>
                    <th className="px-5 py-3.5">Utilisateur</th>
                    <th className="px-4 py-3.5">Rôle</th>
                    <th className="px-4 py-3.5">Organisation</th>
                    <th className="px-4 py-3.5">Contact</th>
                    <th className="px-4 py-3.5">Statut</th>
                    <th className="px-4 py-3.5">Créé le</th>
                    <th className="px-5 py-3.5 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/80">
                  {filtered.map((u) => {
                    const isSelf = currentUser?.id === u.id;
                    return (
                      <tr key={u.id} className="hover:bg-slate-800/40 transition">
                        <td className="px-5 py-3.5">
                          <div className="flex items-center gap-3">
                            {u.avatar_url ? (
                              <img
                                src={u.avatar_url}
                                alt="Avatar"
                                className="h-9 w-9 rounded-full object-cover ring-1 ring-blue-500/30"
                              />
                            ) : (
                              <div className="flex h-9 w-9 items-center justify-center rounded-full bg-gradient-to-br from-blue-600 to-cyan-500 text-xs font-bold text-white shadow-sm">
                                {u.first_name?.[0]}
                                {u.last_name?.[0]}
                              </div>
                            )}
                            <div>
                              <p className="font-semibold text-white">
                                {u.first_name} {u.last_name}
                                {isSelf && (
                                  <span className="ml-1.5 rounded bg-blue-500/20 px-1.5 py-0.5 text-[10px] font-bold text-blue-400">
                                    Vous
                                  </span>
                                )}
                              </p>
                              <p className="text-xs text-slate-400 flex items-center gap-1">
                                <Mail className="h-3 w-3 text-slate-500" /> {u.email}
                              </p>
                            </div>
                          </div>
                        </td>

                        <td className="px-4 py-3.5">
                          <span
                            className={[
                              "inline-flex items-center gap-1 rounded-md px-2.5 py-1 text-xs font-bold border",
                              u.role === "ADMIN"
                                ? "bg-purple-500/20 text-purple-300 border-purple-500/30"
                                : u.role === "MANAGER"
                                ? "bg-blue-500/20 text-blue-300 border-blue-500/30"
                                : "bg-emerald-500/20 text-emerald-300 border-emerald-500/30",
                            ].join(" ")}
                          >
                            <Shield className="h-3 w-3" /> {u.role}
                          </span>
                        </td>

                        <td className="px-4 py-3.5">
                          {u.organization ? (
                            <div>
                              <p className="font-medium text-slate-200">{u.organization.name}</p>
                              <p className="text-xs text-slate-500">
                                {u.organization.city}, {u.organization.country}
                              </p>
                            </div>
                          ) : (
                            <span className="text-xs text-slate-500 italic">Plateforme centrale</span>
                          )}
                        </td>

                        <td className="px-4 py-3.5 text-xs text-slate-400">
                          {u.phone ? (
                            <span className="flex items-center gap-1">
                              <Phone className="h-3 w-3 text-slate-500" /> {u.phone}
                            </span>
                          ) : (
                            <span className="text-slate-600">—</span>
                          )}
                        </td>

                        <td className="px-4 py-3.5">
                          {u.account_status === "INVITED" ? (
                            <Badge variant="warning">Invité</Badge>
                          ) : u.is_active ? (
                            <Badge variant="success">Actif</Badge>
                          ) : (
                            <Badge variant="danger">Désactivé</Badge>
                          )}
                        </td>

                        <td className="px-4 py-3.5 text-xs text-slate-500">
                          {new Date(u.created_at).toLocaleDateString("fr-FR")}
                        </td>

                        <td className="px-5 py-3.5 text-right">
                          <div className="flex items-center justify-end gap-1.5">
                            {/* Enable/Disable toggle */}
                            <button
                              disabled={isSelf || actionId === u.id}
                              onClick={() => toggleStatus(u)}
                              title={u.is_active ? "Désactiver le compte" : "Activer le compte"}
                              className={[
                                "rounded-lg p-1.5 transition",
                                u.is_active
                                  ? "text-slate-400 hover:bg-amber-500/10 hover:text-amber-400"
                                  : "text-slate-400 hover:bg-emerald-500/10 hover:text-emerald-400",
                                isSelf ? "opacity-30 cursor-not-allowed" : "",
                              ].join(" ")}
                            >
                              <Power className="h-4 w-4" />
                            </button>

                            {/* Delete button */}
                            <button
                              disabled={isSelf}
                              onClick={() => setDeleteTarget(u)}
                              title="Supprimer définitivement"
                              className={[
                                "rounded-lg p-1.5 text-slate-400 hover:bg-red-500/10 hover:text-red-400 transition",
                                isSelf ? "opacity-30 cursor-not-allowed" : "",
                              ].join(" ")}
                            >
                              <Trash2 className="h-4 w-4" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>

      {/* Delete Confirmation Modal */}
      {deleteTarget && (
        <Modal
          title="Confirmer la suppression"
          description={`Êtes-vous sûr de vouloir supprimer définitivement le compte de ${deleteTarget.first_name} ${deleteTarget.last_name} (${deleteTarget.email}) ? Cette action est irréversible.`}
          onClose={() => setDeleteTarget(null)}
        >
          <div className="flex justify-end gap-3 pt-3">
            <Button variant="outline" onClick={() => setDeleteTarget(null)}>
              Annuler
            </Button>
            <Button variant="danger" loading={deleting} onClick={confirmDelete}>
              <Trash2 className="h-4 w-4 mr-1" /> Supprimer définitivement
            </Button>
          </div>
        </Modal>
      )}
    </div>
  );
}
