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
      .catch(() => notify("Unable to load users.", "error"))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const toggleStatus = async (user: AdminUser) => {
    setActionId(user.id);
    const action = user.is_active ? "disable" : "enable";
    try {
      await patch(`/admin/users/${user.id}/status`, { action });
      notify(action === "enable" ? "Account reactivated." : "Account disabled.");
      load();
    } catch (err) {
      notify(err instanceof Error ? err.message : "Update error.", "error");
    } finally {
      setActionId(null);
    }
  };

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await del(`/admin/users/${deleteTarget.id}`);
      notify(`Account of ${deleteTarget.first_name} ${deleteTarget.last_name} deleted.`);
      setDeleteTarget(null);
      load();
    } catch (err) {
      notify(err instanceof Error ? err.message : "Unable to delete.", "error");
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
        title="User Account Management"
        subtitle="Access control, activation/deactivation and role administration"
        onMenu={openMobileMenu}
      />

      <div className="p-6 space-y-6">
        {/* Search & Filter Bar */}
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
            <input
              type="text"
              placeholder="Search by name, email, company..."
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
              <option value="ALL">All roles</option>
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
              <option value="ALL">All statuses</option>
              <option value="ACTIVE">Active</option>
              <option value="DISABLED">Disabled</option>
              <option value="INVITED">Invited</option>
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
              title="No users found"
              description="Modify your search criteria or filters."
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm text-slate-300">
                <thead className="border-b border-slate-800 bg-slate-900/60 text-xs font-semibold uppercase tracking-wider text-slate-400">
                  <tr>
                    <th className="px-5 py-3.5">User</th>
                    <th className="px-4 py-3.5">Role</th>
                    <th className="px-4 py-3.5">Organization</th>
                    <th className="px-4 py-3.5">Contact</th>
                    <th className="px-4 py-3.5">Status</th>
                    <th className="px-4 py-3.5">Created</th>
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
                                    You
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
                            <span className="text-xs text-slate-500 italic">Central platform</span>
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
                            <Badge variant="warning">Invited</Badge>
                          ) : u.is_active ? (
                            <Badge variant="success">Active</Badge>
                          ) : (
                            <Badge variant="danger">Disabled</Badge>
                          )}
                        </td>

                        <td className="px-4 py-3.5 text-xs text-slate-500">
                          {new Date(u.created_at).toLocaleDateString("en-US")}
                        </td>

                        <td className="px-5 py-3.5 text-right">
                          <div className="flex items-center justify-end gap-1.5">
                            {/* Enable/Disable toggle */}
                            <button
                              disabled={isSelf || actionId === u.id}
                              onClick={() => toggleStatus(u)}
                              title={u.is_active ? "Disable account" : "Enable account"}
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
                              title="Permanently delete"
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
          title="Confirm deletion"
          description={`Are you sure you want to permanently delete the account of ${deleteTarget.first_name} ${deleteTarget.last_name} (${deleteTarget.email})? This action cannot be undone.`}
          onClose={() => setDeleteTarget(null)}
        >
          <div className="flex justify-end gap-3 pt-3">
            <Button variant="outline" onClick={() => setDeleteTarget(null)}>
              Cancel
            </Button>
            <Button variant="danger" loading={deleting} onClick={confirmDelete}>
              <Trash2 className="h-4 w-4 mr-1" /> Permanently delete
            </Button>
          </div>
        </Modal>
      )}
    </div>
  );
}
