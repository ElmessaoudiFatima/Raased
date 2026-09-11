"use client";

import { useEffect, useState } from "react";
import {
  Check,
  CheckCircle2,
  Copy,
  Edit2,
  Mail,
  MailPlus,
  Phone,
  Power,
  RefreshCw,
  Trash2,
  Truck,
  UserPlus,
} from "lucide-react";
import { Topbar } from "@/components/Topbar";
import { Badge, Button, Card, EmptyState, Input, Modal, Spinner } from "@/components/ui";
import { useShell } from "@/components/ShellContext";
import { useToast } from "@/components/Toasts";
import { del, get, patch, post } from "@/lib/api";

interface Driver {
  id: string;
  first_name: string;
  last_name: string;
  email: string;
  phone?: string | null;
  account_status: string;
  is_active: boolean;
  email_verified: boolean;
  created_at?: string | null;
}

export default function DriversPage() {
  const { openMobileMenu } = useShell();
  const { notify } = useToast();

  const [drivers, setDrivers] = useState<Driver[]>([]);
  const [loading, setLoading] = useState(true);

  // Add modal
  const [addOpen, setAddOpen] = useState(false);
  const [addSaving, setAddSaving] = useState(false);
  const [form, setForm] = useState({ first_name: "", last_name: "", email: "", phone: "" });
  const [addError, setAddError] = useState("");

  // Edit modal
  const [editTarget, setEditTarget] = useState<Driver | null>(null);
  const [editForm, setEditForm] = useState({ first_name: "", last_name: "", email: "", phone: "" });
  const [editSaving, setEditSaving] = useState(false);
  const [editError, setEditError] = useState("");

  // Delete modal
  const [deleteTarget, setDeleteTarget] = useState<Driver | null>(null);
  const [deleting, setDeleting] = useState(false);

  // Invitation Link Modal (Fail-safe for SMTP)
  const [inviteModal, setInviteModal] = useState<{ link: string; driverName: string } | null>(null);
  const [copied, setCopied] = useState(false);

  const [actionId, setActionId] = useState<string | null>(null);

  const load = () => {
    setLoading(true);
    get<{ drivers: Driver[] }>("/managers/drivers")
      .then((d) => setDrivers(d.drivers))
      .catch(() => notify("Impossible de charger les chauffeurs.", "error"))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  // Create driver
  const create = async () => {
    setAddError("");
    setAddSaving(true);
    try {
      const data = await post<{ driver: Driver; invitation_link?: string; message: string }>(
        "/managers/drivers",
        form
      );
      notify("Chauffeur créé avec succès !");
      setAddOpen(false);
      const name = `${form.first_name} ${form.last_name}`;
      setForm({ first_name: "", last_name: "", email: "", phone: "" });
      load();

      // Show instant invitation link modal
      if (data.invitation_link) {
        setInviteModal({
          link: data.invitation_link,
          driverName: name,
        });
      }
    } catch (err) {
      setAddError(err instanceof Error ? err.message : "Création impossible.");
    } finally {
      setAddSaving(false);
    }
  };

  // Open Edit Modal
  const openEdit = (d: Driver) => {
    setEditTarget(d);
    setEditForm({
      first_name: d.first_name,
      last_name: d.last_name,
      email: d.email,
      phone: d.phone || "",
    });
    setEditError("");
  };

  // Save Edit
  const saveEdit = async () => {
    if (!editTarget) return;
    setEditError("");
    setEditSaving(true);
    try {
      await patch(`/managers/drivers/${editTarget.id}`, editForm);
      notify("Chauffeur mis à jour avec succès !");
      setEditTarget(null);
      load();
    } catch (err) {
      setEditError(err instanceof Error ? err.message : "Échec de la modification.");
    } finally {
      setEditSaving(false);
    }
  };

  // Delete driver
  const confirmDelete = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await del(`/managers/drivers/${deleteTarget.id}`);
      notify(`Chauffeur ${deleteTarget.first_name} ${deleteTarget.last_name} supprimé.`);
      setDeleteTarget(null);
      load();
    } catch (err) {
      notify(err instanceof Error ? err.message : "Échec de la suppression.", "error");
    } finally {
      setDeleting(false);
    }
  };

  // Resend invitation
  const resend = async (driver: Driver) => {
    setActionId(driver.id);
    try {
      const data = await post<{ invitation_link?: string; message: string }>(
        `/managers/drivers/${driver.id}/resend-invitation`
      );
      notify("Email d'invitation renvoyé.");
      if (data.invitation_link) {
        setInviteModal({
          link: data.invitation_link,
          driverName: `${driver.first_name} ${driver.last_name}`,
        });
      }
    } catch (err) {
      notify(err instanceof Error ? err.message : "Échec de l'envoi.", "error");
    } finally {
      setActionId(null);
    }
  };

  // Toggle active status
  const toggle = async (d: Driver) => {
    setActionId(d.id);
    try {
      await patch(`/managers/drivers/${d.id}/status`, {
        action: d.is_active ? "disable" : "enable",
      });
      notify(d.is_active ? "Chauffeur désactivé." : "Chauffeur réactivé.");
      load();
    } catch (err) {
      notify(err instanceof Error ? err.message : "Échec de la mise à jour.", "error");
    } finally {
      setActionId(null);
    }
  };

  const copyLink = () => {
    if (!inviteModal) return;
    navigator.clipboard.writeText(inviteModal.link);
    setCopied(true);
    setTimeout(() => setCopied(false), 3000);
  };

  return (
    <div>
      <Topbar
        title="Gestion des Chauffeurs"
        subtitle="Ajout, modification, suppression et suivi des accès de vos conducteurs"
        onMenu={openMobileMenu}
      />

      <div className="p-6 space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-sm text-slate-400">
            {drivers.length} chauffeur(s) enregistré(s) dans votre flotte
          </p>

          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={load} loading={loading}>
              <RefreshCw className="h-3.5 w-3.5 mr-1" /> Actualiser
            </Button>
            <Button variant="figma" onClick={() => setAddOpen(true)}>
              <UserPlus className="h-4 w-4 mr-1.5" /> Inviter un chauffeur
            </Button>
          </div>
        </div>

        {/* Table of Drivers */}
        <Card className="overflow-hidden border-slate-800 bg-[#0f172a]">
          {loading ? (
            <div className="flex h-64 items-center justify-center">
              <Spinner />
            </div>
          ) : drivers.length === 0 ? (
            <EmptyState
              icon={<Truck className="h-8 w-8" />}
              title="Aucun chauffeur"
              description="Commencez par ajouter votre premier conducteur de flotte."
              action={
                <Button variant="figma" onClick={() => setAddOpen(true)}>
                  <UserPlus className="h-4 w-4 mr-1" /> Inviter un chauffeur
                </Button>
              }
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm text-slate-300">
                <thead className="border-b border-slate-800 bg-slate-900/60 text-xs font-semibold uppercase tracking-wider text-slate-400">
                  <tr>
                    <th className="px-5 py-3.5">Chauffeur</th>
                    <th className="px-4 py-3.5">Email</th>
                    <th className="px-4 py-3.5">Téléphone</th>
                    <th className="px-4 py-3.5">Statut Compte</th>
                    <th className="px-4 py-3.5">Disponibilité</th>
                    <th className="px-5 py-3.5 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/80">
                  {drivers.map((d) => (
                    <tr key={d.id} className="hover:bg-slate-800/40 transition">
                      <td className="px-5 py-3.5 font-semibold text-white">
                        <div className="flex items-center gap-3">
                          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-gradient-to-br from-blue-600 to-cyan-500 text-xs font-bold text-white shadow">
                            {d.first_name?.[0]}
                            {d.last_name?.[0]}
                          </div>
                          <div>
                            <p>{d.first_name} {d.last_name}</p>
                            <p className="text-[11px] text-slate-500">Inscrit le {d.created_at ? new Date(d.created_at).toLocaleDateString("fr-FR") : "—"}</p>
                          </div>
                        </div>
                      </td>

                      <td className="px-4 py-3.5 text-xs text-slate-300">
                        <span className="flex items-center gap-1.5">
                          <Mail className="h-3.5 w-3.5 text-slate-500" /> {d.email}
                        </span>
                      </td>

                      <td className="px-4 py-3.5 text-xs text-slate-400">
                        {d.phone ? (
                          <span className="flex items-center gap-1.5">
                            <Phone className="h-3.5 w-3.5 text-slate-500" /> {d.phone}
                          </span>
                        ) : (
                          <span className="text-slate-600">—</span>
                        )}
                      </td>

                      <td className="px-4 py-3.5">
                        {d.account_status === "INVITED" ? (
                          <div className="flex items-center gap-2">
                            <Badge variant="warning">Invitation en attente</Badge>
                            <button
                              disabled={actionId === d.id}
                              onClick={() => resend(d)}
                              className="text-xs text-blue-400 hover:underline inline-flex items-center gap-1"
                              title="Renvoyer l'email d'invitation"
                            >
                              <MailPlus className="h-3 w-3" /> Relancer
                            </button>
                          </div>
                        ) : (
                          <Badge variant="success">Compte actif</Badge>
                        )}
                      </td>

                      <td className="px-4 py-3.5">
                        <button
                          disabled={actionId === d.id}
                          onClick={() => toggle(d)}
                          className="group inline-flex items-center gap-1.5 text-xs transition"
                        >
                          <span
                            className={[
                              "h-2 w-2 rounded-full",
                              d.is_active ? "bg-emerald-400 shadow-sm shadow-emerald-400/50" : "bg-slate-500",
                            ].join(" ")}
                          />
                          <span className="text-slate-300 group-hover:text-white">
                            {d.is_active ? "Opérationnel" : "Désactivé"}
                          </span>
                        </button>
                      </td>

                      <td className="px-5 py-3.5 text-right">
                        <div className="flex items-center justify-end gap-1.5">
                          {/* Edit button */}
                          <button
                            onClick={() => openEdit(d)}
                            title="Modifier les coordonnées"
                            className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-800 hover:text-white transition"
                          >
                            <Edit2 className="h-4 w-4" />
                          </button>

                          {/* Toggle status */}
                          <button
                            disabled={actionId === d.id}
                            onClick={() => toggle(d)}
                            title={d.is_active ? "Désactiver le chauffeur" : "Réactiver le chauffeur"}
                            className="rounded-lg p-1.5 text-slate-400 hover:bg-amber-500/10 hover:text-amber-400 transition"
                          >
                            <Power className="h-4 w-4" />
                          </button>

                          {/* Delete button */}
                          <button
                            onClick={() => setDeleteTarget(d)}
                            title="Supprimer définitivement"
                            className="rounded-lg p-1.5 text-slate-400 hover:bg-red-500/10 hover:text-red-400 transition"
                          >
                            <Trash2 className="h-4 w-4" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>

      {/* Add Driver Modal */}
      {addOpen && (
        <Modal
          title="Inviter un nouveau chauffeur"
          description="Renseignez les coordonnées du chauffeur. Un lien d'invitation sécurisé sera généré pour définir son mot de passe."
          onClose={() => setAddOpen(false)}
        >
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <Input
                label="Prénom"
                required
                value={form.first_name}
                onChange={(e) => setForm({ ...form, first_name: e.target.value })}
              />
              <Input
                label="Nom"
                required
                value={form.last_name}
                onChange={(e) => setForm({ ...form, last_name: e.target.value })}
              />
            </div>
            <Input
              label="Adresse e-mail"
              type="email"
              required
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
            />
            <Input
              label="Téléphone portable"
              placeholder="+212 600 00 00 00"
              value={form.phone}
              onChange={(e) => setForm({ ...form, phone: e.target.value })}
            />

            {addError && (
              <div className="rounded-xl border border-red-500/30 bg-red-950/40 p-3 text-xs text-red-300">
                {addError}
              </div>
            )}

            <div className="flex justify-end gap-3 pt-2">
              <Button variant="outline" onClick={() => setAddOpen(false)}>
                Annuler
              </Button>
              <Button variant="figma" loading={addSaving} onClick={create}>
                Envoyer l'invitation
              </Button>
            </div>
          </div>
        </Modal>
      )}

      {/* Edit Driver Modal */}
      {editTarget && (
        <Modal
          title={`Modifier le chauffeur : ${editTarget.first_name} ${editTarget.last_name}`}
          description="Mettez à jour les coordonnées et les informations de contact."
          onClose={() => setEditTarget(null)}
        >
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <Input
                label="Prénom"
                required
                value={editForm.first_name}
                onChange={(e) => setEditForm({ ...editForm, first_name: e.target.value })}
              />
              <Input
                label="Nom"
                required
                value={editForm.last_name}
                onChange={(e) => setEditForm({ ...editForm, last_name: e.target.value })}
              />
            </div>
            <Input
              label="Adresse e-mail"
              type="email"
              required
              value={editForm.email}
              onChange={(e) => setEditForm({ ...editForm, email: e.target.value })}
            />
            <Input
              label="Téléphone portable"
              placeholder="+212 600 00 00 00"
              value={editForm.phone}
              onChange={(e) => setEditForm({ ...editForm, phone: e.target.value })}
            />

            {editError && (
              <div className="rounded-xl border border-red-500/30 bg-red-950/40 p-3 text-xs text-red-300">
                {editError}
              </div>
            )}

            <div className="flex justify-end gap-3 pt-2">
              <Button variant="outline" onClick={() => setEditTarget(null)}>
                Annuler
              </Button>
              <Button variant="figma" loading={editSaving} onClick={saveEdit}>
                Enregistrer
              </Button>
            </div>
          </div>
        </Modal>
      )}

      {/* Delete Driver Modal */}
      {deleteTarget && (
        <Modal
          title="Supprimer ce chauffeur"
          description={`Êtes-vous certain de vouloir supprimer définitivement le compte de ${deleteTarget.first_name} ${deleteTarget.last_name} (${deleteTarget.email}) ? Les cargaisons assignées seront automatiquement désassignées.`}
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

      {/* Instant Invitation Link Modal */}
      {inviteModal && (
        <Modal
          title="Invitation Chauffeur Prête !"
          description={`L'invitation pour ${inviteModal.driverName} a été générée. Vous pouvez lui transmettre ce lien directement (utile si votre boîte e-mail locale ne délivre pas les courriels) :`}
          onClose={() => setInviteModal(null)}
        >
          <div className="space-y-4">
            <div className="rounded-xl border border-blue-500/30 bg-blue-950/30 p-3 text-xs text-blue-200 break-all font-mono">
              {inviteModal.link}
            </div>

            <div className="flex justify-between items-center pt-2">
              <span className="text-xs text-slate-400">Valable 48 heures</span>
              <div className="flex gap-2">
                <Button variant="outline" onClick={() => setInviteModal(null)}>
                  Fermer
                </Button>
                <Button variant="figma" onClick={copyLink} className="flex items-center gap-1.5">
                  {copied ? (
                    <>
                      <Check className="h-4 w-4 text-emerald-400" /> Lien copié !
                    </>
                  ) : (
                    <>
                      <Copy className="h-4 w-4" /> Copier le lien
                    </>
                  )}
                </Button>
              </div>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}
