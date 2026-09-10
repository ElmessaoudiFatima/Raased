"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft,
  Building2,
  Check,
  Download,
  FileText,
  Mail,
  MapPin,
  Phone,
  UserRound,
  X,
} from "lucide-react";
import { Topbar } from "@/components/Topbar";
import { Badge, Button, Card, Modal, Spinner, Textarea } from "@/components/ui";
import { useShell } from "@/components/ShellContext";
import { useToast } from "@/components/Toasts";
import { get, openPdfWithAuth, patch } from "@/lib/api";

interface OrgDetail {
  id: string;
  name: string;
  legal_id: string;
  country: string;
  city: string;
  phone: string;
  email: string;
  website?: string | null;
  address?: string;
  status: string;
  rejection_reason?: string | null;
  created_at?: string | null;
  managers: {
    id: string;
    first_name: string;
    last_name: string;
    email: string;
    job_title?: string | null;
    email_verified: boolean;
    account_status: string;
  }[];
  documents: {
    id: string;
    document_type: string;
    download_url: string;
    uploaded_at?: string | null;
  }[];
}

export default function OrgDetailPage() {
  const { openMobileMenu } = useShell();
  const { notify } = useToast();
  const router = useRouter();
  const params = useParams();
  const id = params.id as string;

  const [org, setOrg] = useState<OrgDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [rejectOpen, setRejectOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    get<{ organization: OrgDetail }>(`/admin/organizations/${id}`)
      .then((d) => setOrg(d.organization))
      .catch(() => notify("Impossible de charger la demande.", "error"))
      .finally(() => setLoading(false));
  }, [id, notify]);

  useEffect(() => {
    load();
  }, [load]);

  const approve = async () => {
    setBusy(true);
    try {
      await patch(`/admin/organizations/${id}/approve`);
      notify("Demande approuvée.");
      load();
    } catch (err) {
      notify(err instanceof Error ? err.message : "Échec de l'approbation.", "error");
    } finally {
      setBusy(false);
    }
  };

  const reject = async () => {
    setBusy(true);
    try {
      await patch(`/admin/organizations/${id}/reject`, { rejection_reason: reason });
      notify("Demande rejetée.");
      setRejectOpen(false);
      load();
    } catch (err) {
      notify(err instanceof Error ? err.message : "Échec du rejet.", "error");
    } finally {
      setBusy(false);
    }
  };

  if (loading) {
    return (
      <div>
        <Topbar title="Demande d'entreprise" onMenu={openMobileMenu} />
        <div className="flex h-40 items-center justify-center p-6">
          <Spinner className="h-7 w-7 text-raased-teal" />
        </div>
      </div>
    );
  }

  if (!org) {
    return (
      <div>
        <Topbar title="Demande introuvable" onMenu={openMobileMenu} />
        <div className="p-6">
          <p className="text-sm text-slate-500">Cette demande n'existe plus.</p>
        </div>
      </div>
    );
  }

  return (
    <div>
      <Topbar title={org.name} subtitle="Détail de la demande d'entreprise" onMenu={openMobileMenu} />
      <div className="p-6">
        <button
          onClick={() => router.push("/dashboard/admin/organizations")}
          className="mb-5 inline-flex items-center gap-1.5 text-sm font-medium text-slate-500 hover:text-raased-teal"
        >
          <ArrowLeft className="h-4 w-4" /> Retour aux demandes
        </button>

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <div className="space-y-6 lg:col-span-2">
            <Card className="p-6">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-4">
                  <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-raased-navy/5 text-raased-navy">
                    <Building2 className="h-7 w-7" />
                  </div>
                  <div>
                    <h3 className="text-xl font-bold text-raased-navy">{org.name}</h3>
                    <p className="text-sm text-slate-500">ICE / RC : {org.legal_id}</p>
                  </div>
                </div>
                <Badge value={org.status} />
              </div>

              <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2">
                <InfoItem icon={<MapPin className="h-4 w-4" />} label="Localisation" value={`${org.city}, ${org.country}`} />
                <InfoItem icon={<Phone className="h-4 w-4" />} label="Téléphone" value={org.phone} />
                <InfoItem icon={<Mail className="h-4 w-4" />} label="E-mail de contact" value={org.email} />
                <InfoItem icon={<Building2 className="h-4 w-4" />} label="Site web" value={org.website || "—"} />
              </div>
              <div className="mt-4 border-t border-slate-100 pt-4">
                <p className="label">Adresse</p>
                <p className="text-sm text-slate-600">{org.address || "—"}</p>
              </div>

              {org.rejection_reason && (
                <div className="mt-4 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
                  <b>Motif du rejet :</b> {org.rejection_reason}
                </div>
              )}
            </Card>

            <Card className="p-6">
              <h3 className="mb-4 font-bold text-raased-navy">Managers de l'entreprise</h3>
              <div className="space-y-3">
                {org.managers.map((m) => (
                  <div key={m.id} className="flex items-center justify-between rounded-xl border border-slate-100 p-4">
                    <div className="flex items-center gap-3">
                      <UserRound className="h-5 w-5 text-raased-teal" />
                      <div>
                        <p className="text-sm font-semibold text-slate-700">
                          {m.first_name} {m.last_name}
                        </p>
                        <p className="text-xs text-slate-400">
                          {m.email} {m.job_title ? `· ${m.job_title}` : ""}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {m.email_verified ? (
                        <span className="badge bg-emerald-100 text-emerald-700">E-mail vérifié</span>
                      ) : (
                        <Badge value="INVITED" />
                      )}
                    </div>
                  </div>
                ))}
                {org.managers.length === 0 && <p className="text-sm text-slate-400">Aucun manager.</p>}
              </div>
            </Card>

            {org.documents.length > 0 && (
              <Card className="p-6">
                <h3 className="mb-4 font-bold text-raased-navy">Documents justificatifs</h3>
                <div className="space-y-3">
                  {org.documents.map((d) => (
                    <button
                      key={d.id}
                      onClick={() => openPdfWithAuth(d.download_url).catch(() => notify("Impossible d'ouvrir le document.", "error"))}
                      className="flex w-full items-center justify-between rounded-xl border border-slate-100 p-4 text-left transition hover:border-raased-teal"
                    >
                      <div className="flex items-center gap-3">
                        <FileText className="h-5 w-5 text-raased-teal" />
                        <div>
                          <p className="text-sm font-semibold text-slate-700">
                            {d.document_type === "COMPANY_CERTIFICATE"
                              ? "Certificat de l'entreprise"
                              : "Pièce d'identité du responsable"}
                          </p>
                          <p className="text-xs text-slate-400">
                            {d.uploaded_at ? new Date(d.uploaded_at).toLocaleString("fr-FR") : ""}
                          </p>
                        </div>
                      </div>
                      <Download className="h-4 w-4 text-slate-400" />
                    </button>
                  ))}
                </div>
              </Card>
            )}
          </div>

          <div className="space-y-4">
            {org.status === "PENDING" && (
              <Card className="p-5">
                <h3 className="mb-3 font-bold text-raased-navy">Décision</h3>
                <p className="mb-4 text-sm text-slate-500">
                  Validez la demande pour activer l'accès de l'entreprise et de ses managers.
                </p>
                <Button onClick={approve} loading={busy} className="w-full py-3">
                  <Check className="h-4 w-4" /> Approuver la demande
                </Button>
                <Button
                  variant="danger"
                  onClick={() => setRejectOpen(true)}
                  className="mt-3 w-full py-3"
                >
                  <X className="h-4 w-4" /> Rejeter la demande
                </Button>
              </Card>
            )}
            {org.status !== "PENDING" && (
              <Card className="p-5">
                <p className="text-sm text-slate-500">
                  Cette demande a été {org.status === "APPROVED" ? "approuvée" : "rejetée"}.
                </p>
              </Card>
            )}
          </div>
        </div>

        <Modal open={rejectOpen} onClose={() => setRejectOpen(false)} title="Rejeter la demande">
          <div className="space-y-4">
            <Textarea
              label="Motif du rejet"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="Documents insuffisants…"
            />
            <div className="flex justify-end gap-3">
              <Button variant="outline" onClick={() => setRejectOpen(false)}>
                Annuler
              </Button>
              <Button variant="danger" loading={busy} onClick={reject}>
                Confirmer le rejet
              </Button>
            </div>
          </div>
        </Modal>
      </div>
    </div>
  );
}

function InfoItem({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="flex items-start gap-3">
      <div className="mt-0.5 flex h-8 w-8 items-center justify-center rounded-lg bg-slate-50 text-raased-teal">
        {icon}
      </div>
      <div>
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">{label}</p>
        <p className="text-sm font-medium text-slate-700">{value}</p>
      </div>
    </div>
  );
}