"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Building2, Check, Eye, X } from "lucide-react";
import { Topbar } from "@/components/Topbar";
import { Badge, Card, EmptyState, Modal, Spinner, Button, Textarea } from "@/components/ui";
import { useShell } from "@/components/ShellContext";
import { useToast } from "@/components/Toasts";
import { get, patch } from "@/lib/api";

interface OrgRow {
  id: string;
  name: string;
  city: string;
  country: string;
  email: string;
  phone: string;
  status: string;
  created_at?: string | null;
  manager?: { first_name: string; last_name: string; email: string; job_title?: string | null } | null;
  documents_count?: number;
}

type Filter = "PENDING" | "APPROVED" | "REJECTED" | "";

export default function AdminOrganizations() {
  const { openMobileMenu } = useShell();
  const { notify } = useToast();
  const router = useRouter();
  const [orgs, setOrgs] = useState<OrgRow[]>([]);
  const [filter, setFilter] = useState<Filter>("PENDING");
  const [loading, setLoading] = useState(true);
  const [rejecting, setRejecting] = useState<OrgRow | null>(null);
  const [reason, setReason] = useState("");
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    get<{ organizations: OrgRow[] }>("/admin/organizations", {
      ...(filter ? { status: filter } : {}),
    })
      .then((d) => setOrgs(d.organizations))
      .catch(() => notify("Impossible de charger les demandes.", "error"))
      .finally(() => setLoading(false));
  }, [filter, notify]);

  useEffect(() => {
    load();
  }, [load]);

  const approve = async (org: OrgRow) => {
    setBusyId(org.id);
    try {
      await patch(`/admin/organizations/${org.id}/approve`);
      notify(`${org.name} approuvée.`);
      load();
    } catch (err) {
      notify(err instanceof Error ? err.message : "Échec.", "error");
    } finally {
      setBusyId(null);
    }
  };

  const reject = async () => {
    if (!rejecting) return;
    setBusyId(rejecting.id);
    try {
      await patch(`/admin/organizations/${rejecting.id}/reject`, {
        rejection_reason: reason,
      });
      notify(`${rejecting.name} rejetée.`);
      setRejecting(null);
      setReason("");
      load();
    } catch (err) {
      notify(err instanceof Error ? err.message : "Échec.", "error");
    } finally {
      setBusyId(null);
    }
  };

  const tabs: { key: Filter; label: string }[] = [
    { key: "PENDING", label: "En attente" },
    { key: "APPROVED", label: "Approuvées" },
    { key: "REJECTED", label: "Rejetées" },
    { key: "", label: "Toutes" },
  ];

  return (
    <div>
      <Topbar title="Entreprises" subtitle="Validation des demandes d'accès à Raased" onMenu={openMobileMenu} />
      <div className="p-6">
        <div className="mb-5 flex flex-wrap gap-2">
          {tabs.map((t) => (
            <button
              key={t.key}
              onClick={() => setFilter(t.key)}
              className={[
                "rounded-xl px-4 py-2 text-sm font-semibold transition",
                filter === t.key
                  ? "bg-raased-navy text-white"
                  : "border border-slate-200 bg-white text-slate-600 hover:bg-slate-50",
              ].join(" ")}
            >
              {t.label}
            </button>
          ))}
        </div>

        {loading ? (
          <div className="flex h-40 items-center justify-center">
            <Spinner className="h-7 w-7 text-raased-teal" />
          </div>
        ) : orgs.length === 0 ? (
          <EmptyState
            icon={<Building2 className="h-8 w-8" />}
            title="Aucune demande"
            description="Les nouvelles demandes d'entreprises apparaîtront ici."
          />
        ) : (
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2 xl:grid-cols-3">
            {orgs.map((org) => (
              <Card key={org.id} className="flex flex-col p-5">
                <div className="flex items-start justify-between">
                  <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-raased-navy/5 text-raased-navy">
                    <Building2 className="h-6 w-6" />
                  </div>
                  <Badge value={org.status} />
                </div>
                <h3 className="mt-4 text-base font-bold text-raased-navy">{org.name}</h3>
                <p className="text-sm text-slate-500">
                  {org.city}, {org.country} · {org.email}
                </p>
                {org.manager && (
                  <p className="mt-2 text-xs text-slate-400">
                    Responsable : <b>{org.manager.first_name} {org.manager.last_name}</b>
                    {org.manager.job_title ? ` — ${org.manager.job_title}` : ""}
                  </p>
                )}
                <div className="mt-4 flex flex-1 items-end gap-2">
                  <button
                    onClick={() => router.push(`/dashboard/admin/organizations/${org.id}`)}
                    className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-xl border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-50"
                  >
                    <Eye className="h-3.5 w-3.5" /> Détails
                  </button>
                  {org.status === "PENDING" && (
                    <>
                      <button
                        onClick={() => approve(org)}
                        disabled={busyId === org.id}
                        className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-xl bg-raased-teal px-3 py-2 text-xs font-semibold text-white hover:bg-raased-navy disabled:opacity-50"
                      >
                        <Check className="h-3.5 w-3.5" /> Approuver
                      </button>
                      <button
                        onClick={() => setRejecting(org)}
                        disabled={busyId === org.id}
                        className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-xl bg-raased-alert px-3 py-2 text-xs font-semibold text-white hover:bg-red-700 disabled:opacity-50"
                      >
                        <X className="h-3.5 w-3.5" /> Rejeter
                      </button>
                    </>
                  )}
                </div>
              </Card>
            ))}
          </div>
        )}

        <Modal open={Boolean(rejecting)} onClose={() => setRejecting(null)} title="Rejeter la demande">
          <div className="space-y-4">
            <p className="text-sm text-slate-500">
              Rejeter la demande de <b>{rejecting?.name}</b> ? Les managers associés seront désactivés.
            </p>
            <Textarea
              label="Motif du rejet"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="Documents insuffisants, informations incomplètes…"
            />
            <div className="flex justify-end gap-3">
              <Button variant="outline" onClick={() => setRejecting(null)}>
                Annuler
              </Button>
              <Button variant="danger" loading={busyId === rejecting?.id} onClick={reject}>
                Confirmer le rejet
              </Button>
            </div>
          </div>
        </Modal>
      </div>
    </div>
  );
}