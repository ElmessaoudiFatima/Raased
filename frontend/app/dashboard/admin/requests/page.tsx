"use client";

import { useEffect, useState } from "react";
import {
  Building2,
  CheckCircle2,
  Clock,
  Download,
  Eye,
  FileCheck,
  FileText,
  Globe,
  Mail,
  MapPin,
  Phone,
  RefreshCw,
  ShieldAlert,
  UserCheck,
  XCircle,
} from "lucide-react";
import { Topbar } from "@/components/Topbar";
import { Badge, Button, Card, EmptyState, Modal, Spinner } from "@/components/ui";
import { useShell } from "@/components/ShellContext";
import { useToast } from "@/components/Toasts";
import { get, patch, BACKEND_URL } from "@/lib/api";

interface OrgRequest {
  id: string;
  name: string;
  legal_id: string;
  country: string;
  city: string;
  phone: string;
  email: string;
  website?: string | null;
  status: string;
  created_at: string;
  documents_count: number;
  manager?: {
    id: string;
    first_name: string;
    last_name: string;
    email: string;
    job_title?: string | null;
    phone?: string | null;
    email_verified: boolean;
  } | null;
}

interface OrgDetail extends OrgRequest {
  documents: {
    id: string;
    document_type: string;
    download_url: string;
    uploaded_at: string;
  }[];
}

export default function AdminRequestsPage() {
  const { openMobileMenu } = useShell();
  const { notify } = useToast();

  const [requests, setRequests] = useState<OrgRequest[]>([]);
  const [loading, setLoading] = useState(true);

  const [selectedOrg, setSelectedOrg] = useState<OrgDetail | null>(null);
  const [inspectLoading, setInspectLoading] = useState(false);

  const [rejectModal, setRejectModal] = useState<OrgRequest | null>(null);
  const [rejectReason, setRejectReason] = useState("");
  const [acting, setActing] = useState(false);

  const load = () => {
    setLoading(true);
    get<any>("/admin/organizations?status=PENDING")
      .then((d) => setRequests(Array.isArray(d) ? d : (d?.organizations ?? [])))
      .catch(() => notify("Impossible de charger les demandes.", "error"))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const openInspect = async (orgId: string) => {
    setInspectLoading(true);
    try {
      const data = await get<any>(`/admin/organizations/${orgId}`);
      setSelectedOrg(data?.organization ?? data);
    } catch {
      notify("Impossible de charger les détails.", "error");
    } finally {
      setInspectLoading(false);
    }
  };


  const approve = async (orgId: string, orgName: string) => {
    setActing(true);
    try {
      await patch(`/admin/organizations/${orgId}/approve`);
      notify(`L'organisation ${orgName} a été approuvée avec succès !`);
      setSelectedOrg(null);
      load();
    } catch (err) {
      notify(err instanceof Error ? err.message : "Erreur d'approbation.", "error");
    } finally {
      setActing(false);
    }
  };

  const reject = async () => {
    if (!rejectModal) return;
    setActing(true);
    try {
      await patch(`/admin/organizations/${rejectModal.id}/reject`, {
        rejection_reason: rejectReason || "Dossier non conforme ou incomplet.",
      });
      notify(`Demande de ${rejectModal.name} rejetée.`);
      setRejectModal(null);
      setSelectedOrg(null);
      setRejectReason("");
      load();
    } catch (err) {
      notify(err instanceof Error ? err.message : "Erreur de rejet.", "error");
    } finally {
      setActing(false);
    }
  };

  return (
    <div>
      <Topbar
        title="Demandes de Création de Compte"
        subtitle="Examen des entreprises de transport en attente de validation réglementaire"
        onMenu={openMobileMenu}
      />

      <div className="p-6 space-y-6">
        <div className="flex items-center justify-between">
          <p className="text-sm text-slate-400">
            {(requests || []).length} demande(s) en attente d'approbation
          </p>
          <Button variant="outline" size="sm" onClick={load} loading={loading}>
            <RefreshCw className="h-3.5 w-3.5 mr-1" /> Actualiser
          </Button>
        </div>

        {loading ? (
          <div className="flex h-64 items-center justify-center">
            <Spinner />
          </div>
        ) : (requests || []).length === 0 ? (
          <Card className="p-8 border-slate-800 bg-[#0f172a]">
            <EmptyState
              icon={<CheckCircle2 className="h-10 w-10 text-emerald-400" />}
              title="Toutes les demandes ont été traitées"
              description="Aucun dossier d'adhésion d'entreprise n'est en attente actuellement."
            />
          </Card>
        ) : (
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            {(requests || []).map((org) => (

              <Card key={org.id} className="p-6 border-slate-800 bg-[#0f172a] space-y-5 shadow-lg">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-blue-600/10 text-blue-400 ring-1 ring-blue-500/20">
                      <Building2 className="h-6 w-6" />
                    </div>
                    <div>
                      <h3 className="text-base font-bold text-white">{org.name}</h3>
                      <p className="text-xs text-slate-400 flex items-center gap-1">
                        <MapPin className="h-3 w-3 text-slate-500" /> {org.city}, {org.country} • RC : <span className="font-mono text-slate-300">{org.legal_id}</span>
                      </p>
                    </div>
                  </div>
                  <Badge variant="warning">En attente</Badge>
                </div>

                {/* Manager info */}
                {org.manager && (
                  <div className="rounded-xl border border-slate-800/80 bg-slate-900/60 p-3.5 text-xs space-y-1.5">
                    <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                      Responsable désigné
                    </p>
                    <p className="font-medium text-slate-200">
                      {org.manager.first_name} {org.manager.last_name}
                      {org.manager.job_title && ` (${org.manager.job_title})`}
                    </p>
                    <div className="flex flex-wrap items-center gap-3 text-slate-400">
                      <span className="flex items-center gap-1">
                        <Mail className="h-3 w-3 text-slate-500" /> {org.manager.email}
                      </span>
                      {org.manager.phone && (
                        <span className="flex items-center gap-1">
                          <Phone className="h-3 w-3 text-slate-500" /> {org.manager.phone}
                        </span>
                      )}
                    </div>
                  </div>
                )}

                {/* Footer and Actions */}
                <div className="flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-slate-800">
                  <span className="text-xs text-slate-500 flex items-center gap-1">
                    <Clock className="h-3.5 w-3.5" /> Reçu le {new Date(org.created_at).toLocaleDateString("fr-FR")}
                  </span>

                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => openInspect(org.id)}
                    >
                      <Eye className="h-3.5 w-3.5 mr-1" /> Examiner ({org.documents_count} doc)
                    </Button>
                    <Button
                      variant="figma"
                      size="sm"
                      onClick={() => approve(org.id, org.name)}
                      loading={acting}
                    >
                      <UserCheck className="h-3.5 w-3.5 mr-1" /> Approuver
                    </Button>
                    <Button
                      variant="danger"
                      size="sm"
                      onClick={() => setRejectModal(org)}
                    >
                      <XCircle className="h-3.5 w-3.5 mr-1" /> Rejeter
                    </Button>
                  </div>
                </div>
              </Card>
            ))}
          </div>
        )}
      </div>

      {/* Inspection Modal */}
      {selectedOrg && (
        <Modal
          title={`Dossier : ${selectedOrg.name}`}
          description="Inspection des pièces justificatives et validation réglementaire"
          onClose={() => setSelectedOrg(null)}
        >
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-3 text-xs bg-slate-900/60 p-3 rounded-xl border border-slate-800">
              <div>
                <span className="text-slate-500">Pays / Ville :</span>
                <p className="font-semibold text-white">{selectedOrg.country}, {selectedOrg.city}</p>
              </div>
              <div>
                <span className="text-slate-500">Identifiant Légal (RC) :</span>
                <p className="font-semibold text-white font-mono">{selectedOrg.legal_id}</p>
              </div>
              <div>
                <span className="text-slate-500">Email d'entreprise :</span>
                <p className="font-semibold text-white">{selectedOrg.email}</p>
              </div>
              <div>
                <span className="text-slate-500">Téléphone :</span>
                <p className="font-semibold text-white">{selectedOrg.phone}</p>
              </div>
            </div>

            <div>
              <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">
                Documents Déposés
              </h4>
              {selectedOrg.documents.length === 0 ? (
                <p className="text-xs text-slate-500 italic">Aucun document téléversé pour cette entreprise.</p>
              ) : (
                <div className="space-y-2">
                  {selectedOrg.documents.map((d) => (
                    <div
                      key={d.id}
                      className="flex items-center justify-between rounded-xl border border-slate-800 bg-slate-900/40 p-3 text-xs"
                    >
                      <div className="flex items-center gap-2.5">
                        <FileText className="h-4 w-4 text-blue-400" />
                        <div>
                          <p className="font-semibold text-slate-200">
                            {d.document_type === "COMPANY_CERTIFICATE"
                              ? "Certificat d'immatriculation / RC"
                              : "Pièce d'identité du responsable"}
                          </p>
                          <p className="text-[10px] text-slate-500">
                            Déposé le {new Date(d.uploaded_at).toLocaleDateString("fr-FR")}
                          </p>
                        </div>
                      </div>
                      <a
                        href={`${BACKEND_URL}${d.download_url}`}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1 rounded-lg border border-slate-700 bg-slate-800 px-2.5 py-1 text-xs font-medium text-slate-200 hover:bg-slate-700"
                      >
                        <Download className="h-3 w-3" /> Télécharger
                      </a>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="flex justify-end gap-3 pt-3 border-t border-slate-800">
              <Button variant="outline" onClick={() => setSelectedOrg(null)}>
                Fermer
              </Button>
              <Button
                variant="danger"
                onClick={() => {
                  setRejectModal(selectedOrg);
                  setSelectedOrg(null);
                }}
              >
                Rejeter le dossier
              </Button>
              <Button
                variant="figma"
                loading={acting}
                onClick={() => approve(selectedOrg.id, selectedOrg.name)}
              >
                <CheckCircle2 className="h-4 w-4 mr-1" /> Valider & Activer le compte
              </Button>
            </div>
          </div>
        </Modal>
      )}

      {/* Rejection Modal */}
      {rejectModal && (
        <Modal
          title={`Rejeter la demande : ${rejectModal.name}`}
          description="Veuillez spécifier le motif de refus qui sera notifié à l'entreprise."
          onClose={() => setRejectModal(null)}
        >
          <div className="space-y-4">
            <textarea
              rows={3}
              placeholder="Ex : Document du registre du commerce illisible, numéro RC non correspondant..."
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              className="w-full rounded-xl border border-slate-800 bg-[#0a101d] p-3 text-xs text-slate-200 placeholder:text-slate-500 outline-none focus:border-red-500"
            />
            <div className="flex justify-end gap-3">
              <Button variant="outline" onClick={() => setRejectModal(null)}>
                Annuler
              </Button>
              <Button variant="danger" loading={acting} onClick={reject}>
                Confirmer le refus
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}
