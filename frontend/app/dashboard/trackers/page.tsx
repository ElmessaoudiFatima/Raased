"use client";

import { useEffect, useState } from "react";
import { Radio, RadioTower } from "lucide-react";
import { Topbar } from "@/components/Topbar";
import { Badge, Button, Card, EmptyState, Input, Modal, Spinner } from "@/components/ui";
import { useShell } from "@/components/ShellContext";
import { useToast } from "@/components/Toasts";
import { get, post } from "@/lib/api";

interface TrackerRow {
  id: string;
  device_id: string;
  vehicle_registration?: string | null;
  msisdn?: string | null;
  status: string;
  last_seen_at?: string | null;
}

export default function TrackersPage() {
  const { openMobileMenu } = useShell();
  const { notify } = useToast();
  const [trackers, setTrackers] = useState<TrackerRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [form, setForm] = useState({ device_id: "", vehicle_registration: "", msisdn: "" });

  const load = () => {
    get<any>("/managers/trackers")
      .then((d) => setTrackers(Array.isArray(d) ? d : (d?.trackers ?? [])))
      .catch(() => notify("Impossible de charger les trackers.", "error"))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const create = async () => {
    setError("");
    setSaving(true);
    try {
      await post("/managers/trackers", form);
      notify("Tracker enregistré.");
      setOpen(false);
      setForm({ device_id: "", vehicle_registration: "", msisdn: "" });
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Enregistrement impossible.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div>
      <Topbar title="Trackers" subtitle="Boîtiers de géolocalisation de la flotte" onMenu={openMobileMenu} />
      <div className="p-6">
        <div className="mb-5 flex items-center justify-between">
          <p className="text-sm text-slate-500">{trackers.length} tracker(s)</p>
          <Button onClick={() => setOpen(true)}>
            <RadioTower className="h-4 w-4" /> Enregistrer un tracker
          </Button>
        </div>

        {loading ? (
          <div className="flex h-40 items-center justify-center">
            <Spinner className="h-7 w-7 text-raased-teal" />
          </div>
        ) : trackers.length === 0 ? (
          <EmptyState
            icon={<Radio className="h-8 w-8" />}
            title="Aucun tracker"
            description="Enregistrez un boîtier pour pouvoir suivre vos convois."
          />
        ) : (
          <Card className="overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-slate-100 bg-slate-50/70 text-xs uppercase tracking-wide text-slate-500">
                    <th className="px-5 py-3 font-semibold">Boîtier</th>
                    <th className="px-5 py-3 font-semibold">Véhicule</th>
                    <th className="px-5 py-3 font-semibold">MSISDN (SIM)</th>
                    <th className="px-5 py-3 font-semibold">Statut</th>
                    <th className="px-5 py-3 font-semibold">Dernière activité</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {trackers.map((t) => (
                    <tr key={t.id} className="hover:bg-slate-50/60">
                      <td className="px-5 py-3.5 font-mono text-xs font-semibold text-raased-navy">
                        {t.device_id}
                      </td>
                      <td className="px-5 py-3.5 text-slate-500">
                        {t.vehicle_registration || "—"}
                      </td>
                      <td className="px-5 py-3.5 text-slate-500">{t.msisdn || "—"}</td>
                      <td className="px-5 py-3.5">
                        <Badge value={t.status} />
                      </td>
                      <td className="px-5 py-3.5 text-xs text-slate-400">
                        {t.last_seen_at
                          ? new Date(t.last_seen_at).toLocaleString("fr-FR")
                          : "Jamais"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        )}

        <Modal open={open} onClose={() => setOpen(false)} title="Enregistrer un tracker">
          <div className="space-y-4">
            <Input
              label="Identifiant du boîtier"
              value={form.device_id}
              onChange={(e) => setForm((f) => ({ ...f, device_id: e.target.value }))}
              placeholder="LGT-TRK-007"
            />
            <Input
              label="Immatriculation du véhicule"
              value={form.vehicle_registration}
              onChange={(e) => setForm((f) => ({ ...f, vehicle_registration: e.target.value }))}
              placeholder="12345-A-6"
            />
            <Input
              label="MSISDN (numéro de la SIM)"
              value={form.msisdn}
              onChange={(e) => setForm((f) => ({ ...f, msisdn: e.target.value }))}
              placeholder="+212600000000"
            />
            {error && (
              <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-medium text-red-700">
                {error}
              </div>
            )}
            <div className="flex justify-end gap-3 pt-2">
              <Button variant="outline" onClick={() => setOpen(false)}>
                Annuler
              </Button>
              <Button loading={saving} onClick={create} disabled={!form.device_id}>
                Enregistrer
              </Button>
            </div>
          </div>
        </Modal>
      </div>
    </div>
  );
}