"use client";

import { useEffect, useState } from "react";
import { Boxes, PackagePlus, Play, Truck } from "lucide-react";
import { Topbar } from "@/components/Topbar";
import { Badge, Button, Card, EmptyState, Input, Modal, Select, Spinner } from "@/components/ui";
import { useShell } from "@/components/ShellContext";
import { useToast } from "@/components/Toasts";
import { get, patch, post } from "@/lib/api";

const MOROCCO_CITIES = [
  { city: "Casablanca", lat: 33.5731, lng: -7.5898 },
  { city: "Rabat", lat: 34.0209, lng: -6.8416 },
  { city: "Marrakech", lat: 31.6295, lng: -7.9811 },
  { city: "Agadir", lat: 30.4278, lng: -9.5981 },
  { city: "Tanger", lat: 35.7595, lng: -5.834 },
  { city: "Fès", lat: 34.0181, lng: -5.0078 },
];

interface CargoRow {
  id: string;
  reference: string;
  type: string;
  criticality: string;
  status: string;
  origin: string;
  destination: string;
  origin_lat: number;
  origin_lng: number;
  destination_lat: number;
  destination_lng: number;
  position?: { progress_pct: number; eta_minutes: number } | null;
  tracker?: { id: string; device_id: string; vehicle_registration?: string | null } | null;
  driver?: { id: string; first_name: string; last_name: string } | null;
}

interface TrackerRow {
  id: string;
  device_id: string;
  vehicle_registration?: string | null;
  status: string;
}

export default function CargosPage() {
  const { openMobileMenu } = useShell();
  const { notify } = useToast();
  const [cargos, setCargos] = useState<CargoRow[]>([]);
  const [trackers, setTrackers] = useState<TrackerRow[]>([]);
  const [drivers, setDrivers] = useState<{ id: string; first_name: string; last_name: string; email: string }[]>([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [actionId, setActionId] = useState<string | null>(null);
  const [form, setForm] = useState({
    reference: "",
    type: "GENERAL",
    criticality: "MEDIUM",
    origin: "Casablanca",
    destination: "Marrakech",
    tracker_id: "",
    driver_id: "",
    speed_kmh: "80",
  });

  const load = () => {
    get<any>("/managers/cargos")
      .then((d) => setCargos(Array.isArray(d) ? d : (d?.cargos ?? [])))
      .catch(() => notify("Impossible de charger les cargaisons.", "error"))
      .finally(() => setLoading(false));
    get<any>("/managers/trackers")
      .then((d) => setTrackers(Array.isArray(d) ? d : (d?.trackers ?? [])))
      .catch(() => {});
    get<any>("/managers/drivers")
      .then((d) => setDrivers(Array.isArray(d) ? d : (d?.drivers ?? [])))
      .catch(() => {});
  };

  useEffect(load, []);

  const coordOf = (city: string) => {
    const found = MOROCCO_CITIES.find((c) => c.city === city);
    return found ? { lat: found.lat, lng: found.lng } : { lat: 0, lng: 0 };
  };

  const create = async () => {
    setError("");
    setSaving(true);
    try {
      const o = coordOf(form.origin);
      const d = coordOf(form.destination);
      await post("/managers/cargos", {
        ...form,
        speed_kmh: Number(form.speed_kmh),
        origin_lat: o.lat,
        origin_lng: o.lng,
        destination_lat: d.lat,
        destination_lng: d.lng,
        tracker_id: form.tracker_id || null,
        driver_id: form.driver_id || null,
      });
      notify("Cargaison créée.");
      setOpen(false);
      setForm({ ...form, reference: "" });
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Création impossible.");
    } finally {
      setSaving(false);
    }
  };

  const changeStatus = async (id: string, status: string) => {
    setActionId(id);
    try {
      await patch(`/managers/cargos/${id}/status`, { status });
      notify(status === "DEPART" ? "Convoi lancé." : "Statut mis à jour.");
      load();
    } catch (err) {
      notify(err instanceof Error ? err.message : "Échec de la mise à jour.", "error");
    } finally {
      setActionId(null);
    }
  };

  return (
    <div>
      <Topbar title="Cargaisons" subtitle="Suivi des convois et des livraisons" onMenu={openMobileMenu} />
      <div className="p-6">
        <div className="mb-5 flex items-center justify-between">
          <p className="text-sm text-slate-500">{cargos.length} cargaison(s)</p>
          <Button onClick={() => setOpen(true)}>
            <PackagePlus className="h-4 w-4" /> Nouvelle cargaison
          </Button>
        </div>

        {loading ? (
          <div className="flex h-40 items-center justify-center">
            <Spinner className="h-7 w-7 text-raased-teal" />
          </div>
        ) : cargos.length === 0 ? (
          <EmptyState
            icon={<Boxes className="h-8 w-8" />}
            title="Aucune cargaison"
            description="Créez votre première cargaison et lancez le convoi."
          />
        ) : (
          <Card className="overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-slate-100 bg-slate-50/70 text-xs uppercase tracking-wide text-slate-500">
                    <th className="px-5 py-3 font-semibold">Référence</th>
                    <th className="px-5 py-3 font-semibold">Type</th>
                    <th className="px-5 py-3 font-semibold">Itinéraire</th>
                    <th className="px-5 py-3 font-semibold">Chauffeur</th>
                    <th className="px-5 py-3 font-semibold">Véhicule</th>
                    <th className="px-5 py-3 font-semibold">Criticité</th>
                    <th className="px-5 py-3 font-semibold">Statut</th>
                    <th className="px-5 py-3 text-right font-semibold">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {cargos.map((c) => (
                    <tr key={c.id} className="hover:bg-slate-50/60">
                      <td className="px-5 py-3.5">
                        <p className="font-semibold text-raased-navy">{c.reference}</p>
                        {c.position && (
                          <p className="text-xs text-raased-teal">Progression {c.position.progress_pct}%</p>
                        )}
                      </td>
                      <td className="px-5 py-3.5 text-slate-500">{c.type.replace(/_/g, " ")}</td>
                      <td className="px-5 py-3.5 text-slate-500">
                        {c.origin} → {c.destination}
                      </td>
                      <td className="px-5 py-3.5 text-slate-500">
                        {c.driver ? `${c.driver.first_name} ${c.driver.last_name}` : "Non assigné"}
                      </td>
                      <td className="px-5 py-3.5 text-slate-500">
                        {c.tracker?.vehicle_registration || c.tracker?.device_id || "—"}
                      </td>
                      <td className="px-5 py-3.5">
                        <Badge value={c.criticality} />
                      </td>
                      <td className="px-5 py-3.5">
                        <Badge value={c.status} />
                      </td>
                      <td className="px-5 py-3.5">
                        <div className="flex justify-end">
                          {c.status === "PENDING" && (
                            <button
                              onClick={() => changeStatus(c.id, "DEPART")}
                              disabled={actionId === c.id}
                              className="inline-flex items-center gap-1 rounded-lg bg-raased-teal px-2.5 py-1.5 text-xs font-semibold text-white hover:bg-raased-navy disabled:opacity-50"
                            >
                              <Play className="h-3.5 w-3.5" /> Lancer
                            </button>
                          )}
                          {c.status === "IN_TRANSIT" && (
                            <button
                              onClick={() => changeStatus(c.id, "DELIVERED")}
                              disabled={actionId === c.id}
                              className="inline-flex items-center gap-1 rounded-lg border border-emerald-200 px-2.5 py-1.5 text-xs font-semibold text-emerald-600 hover:bg-emerald-50 disabled:opacity-50"
                            >
                              <Truck className="h-3.5 w-3.5" /> Livré
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        )}

        <Modal open={open} onClose={() => setOpen(false)} title="Nouvelle cargaison" wide>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Input
              label="Référence"
              value={form.reference}
              onChange={(e) => setForm((f) => ({ ...f, reference: e.target.value }))}
              placeholder="CARGO-2026-007"
            />
            <Select
              label="Type de marchandise"
              value={form.type}
              onChange={(e) => setForm((f) => ({ ...f, type: e.target.value }))}
            >
              <option value="GENERAL">Marchandises générales</option>
              <option value="PHARMACEUTICAL">Pharmaceutique</option>
              <option value="ELECTRONICS">Électronique</option>
              <option value="FMCG">Grande consommation</option>
              <option value="TEXTILE">Textile</option>
              <option value="PERISHABLE">Périssable</option>
            </Select>
            <Select
              label="Criticité"
              value={form.criticality}
              onChange={(e) => setForm((f) => ({ ...f, criticality: e.target.value }))}
            >
              <option value="LOW">Faible</option>
              <option value="MEDIUM">Moyenne</option>
              <option value="HIGH">Haute</option>
              <option value="CRITICAL">Critique</option>
            </Select>
            <Input
              label="Vitesse estimée (km/h)"
              type="number"
              value={form.speed_kmh}
              onChange={(e) => setForm((f) => ({ ...f, speed_kmh: e.target.value }))}
            />
            <Select
              label="Départ"
              value={form.origin}
              onChange={(e) => setForm((f) => ({ ...f, origin: e.target.value }))}
            >
              {MOROCCO_CITIES.map((c) => (
                <option key={c.city} value={c.city}>
                  {c.city}
                </option>
              ))}
            </Select>
            <Select
              label="Destination"
              value={form.destination}
              onChange={(e) => setForm((f) => ({ ...f, destination: e.target.value }))}
            >
              {MOROCCO_CITIES.map((c) => (
                <option key={c.city} value={c.city}>
                  {c.city}
                </option>
              ))}
            </Select>
            <Select
              label="Tracker / véhicule"
              value={form.tracker_id}
              onChange={(e) => setForm((f) => ({ ...f, tracker_id: e.target.value }))}
            >
              <option value="">Non assigné</option>
              {trackers.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.vehicle_registration || t.device_id}
                </option>
              ))}
            </Select>
            <Select
              label="Chauffeur"
              value={form.driver_id}
              onChange={(e) => setForm((f) => ({ ...f, driver_id: e.target.value }))}
            >
              <option value="">Non assigné</option>
              {drivers.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.first_name} {d.last_name}
                  </option>
                ))}
            </Select>
          </div>
          {error && (
            <div className="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-medium text-red-700">
              {error}
            </div>
          )}
          <div className="mt-5 flex justify-end gap-3">
            <Button variant="outline" onClick={() => setOpen(false)}>
              Annuler
            </Button>
            <Button loading={saving} onClick={create} disabled={!form.reference}>
              Créer la cargaison
            </Button>
          </div>
        </Modal>
      </div>
    </div>
  );
}