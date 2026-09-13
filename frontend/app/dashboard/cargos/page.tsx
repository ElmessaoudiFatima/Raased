"use client";

import { useEffect, useMemo, useState } from "react";
import { Boxes, CheckCircle2, PackagePlus, Play, Truck, UserCheck } from "lucide-react";
import { Topbar } from "@/components/Topbar";
import { Badge, Button, Card, EmptyState, Modal, Select, Spinner } from "@/components/ui";
import { useShell } from "@/components/ShellContext";
import { useToast } from "@/components/Toasts";
import { get, patch, post } from "@/lib/api";

interface CorridorItem {
  id: string;
  name: string;
  origin: string;
  destination: string;
  risk_level: string;
  is_active?: boolean;
}

interface CargoRow {
  id: string;
  reference: string;
  type: string;
  criticality: string;
  status: string;
  corridor_id?: string;
  driver_id?: string | null;
  origin?: string;
  destination?: string;
  position?: { progress_pct: number; eta_minutes: number } | null;
  tracker?: { id: string; device_id: string; label?: string | null; vehicle_registration?: string | null } | null;
  driver?: { id: string; first_name: string; last_name: string; email?: string } | null;
}

interface TrackerRow {
  id: string;
  device_id: string;
  label?: string | null;
  vehicle_registration?: string | null;
  status: string;
}

export default function CargosPage() {
  const { openMobileMenu } = useShell();
  const { notify } = useToast();
  const [cargos, setCargos] = useState<CargoRow[]>([]);
  const [corridors, setCorridors] = useState<CorridorItem[]>([]);
  const [trackers, setTrackers] = useState<TrackerRow[]>([]);
  const [drivers, setDrivers] = useState<{ id: string; first_name: string; last_name: string; email: string }[]>([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [actionId, setActionId] = useState<string | null>(null);

  // Read-only presentation of newly created cargo reference
  const [createdCargo, setCreatedCargo] = useState<{
    id: string;
    reference: string;
    corridorLabel: string;
    type: string;
    criticality: string;
  } | null>(null);

  const [form, setForm] = useState({
    corridor_id: "",
    type: "GENERAL",
    criticality: "MEDIUM",
    tracker_id: "",
    driver_id: "",
  });

  // Modal d'assignation directe pour une cargaison existante
  const [assignModalOpen, setAssignModalOpen] = useState(false);
  const [assignCargo, setAssignCargo] = useState<CargoRow | null>(null);
  const [assignForm, setAssignForm] = useState({
    driver_id: "",
    tracker_id: "",
  });
  const [savingAssign, setSavingAssign] = useState(false);
  const [assignError, setAssignError] = useState("");

  const handleOpenAssign = (c: CargoRow) => {
    setAssignCargo(c);
    setAssignForm({
      driver_id: c.driver?.id || c.driver_id || "",
      tracker_id: c.tracker?.id || "",
    });
    setAssignError("");
    setAssignModalOpen(true);
  };

  const saveAssign = async () => {
    if (!assignCargo) return;
    setSavingAssign(true);
    setAssignError("");
    try {
      await patch(`/managers/cargos/${assignCargo.id}`, {
        driver_id: assignForm.driver_id || null,
        tracker_id: assignForm.tracker_id || null,
      });
      notify(`Assignment saved for ${assignCargo.reference}!`);
      setAssignModalOpen(false);
      load();
    } catch (err) {
      setAssignError(err instanceof Error ? err.message : "Failed to update assignment.");
    } finally {
      setSavingAssign(false);
    }
  };

  const load = () => {
    get<any>("/managers/cargos")
      .then((d) => setCargos(Array.isArray(d) ? d : (d?.cargos ?? [])))
      .catch(() => notify("Unable to load shipments.", "error"))
      .finally(() => setLoading(false));

    get<any>("/managers/corridors")
      .then((d) => {
        const list = Array.isArray(d) ? d : (d?.corridors ?? []);
        setCorridors(list);
        if (list.length > 0) {
          setForm((f) => (f.corridor_id ? f : { ...f, corridor_id: list[0].id }));
        }
      })
      .catch(() => {});

    get<any>("/managers/trackers")
      .then((d) => setTrackers(Array.isArray(d) ? d : (d?.trackers ?? [])))
      .catch(() => {});

    get<any>("/managers/drivers")
      .then((d) => setDrivers(Array.isArray(d) ? d : (d?.drivers ?? [])))
      .catch(() => {});
  };

  useEffect(load, []);

  // Quick lookup from corridor_id -> corridor details
  const corridorMap = useMemo(() => {
    const map: Record<string, CorridorItem> = {};
    for (const c of corridors) {
      map[c.id] = c;
    }
    return map;
  }, [corridors]);

  const handleOpenModal = () => {
    setCreatedCargo(null);
    setError("");
    if (corridors.length > 0 && !form.corridor_id) {
      setForm((f) => ({ ...f, corridor_id: corridors[0].id }));
    }
    setOpen(true);
  };

  const create = async () => {
    if (!form.corridor_id) {
      setError("Please select a corridor.");
      return;
    }
    setError("");
    setSaving(true);
    try {
      const res = await post<any>("/managers/cargos", {
        corridor_id: form.corridor_id,
        type: form.type,
        criticality: form.criticality,
        driver_id: form.driver_id || undefined,
        tracker_id: form.tracker_id || undefined,
      });

      if (form.tracker_id && res?.id && !res?.tracker) {
        try {
          await post(`/managers/trackers/${form.tracker_id}/assign`, {
            cargo_id: res.id,
          });
        } catch (assignErr) {
          console.warn("Tracker assignment:", assignErr);
        }
      }

      const selCorridor = corridorMap[form.corridor_id];
      const corridorLabel = selCorridor
        ? `${selCorridor.origin} → ${selCorridor.destination}`
        : "Selected corridor";

      setCreatedCargo({
        id: res.id,
        reference: res.reference,
        corridorLabel,
        type: res.type || form.type,
        criticality: res.criticality || form.criticality,
      });

      notify(`Shipment created! Reference generated: ${res.reference}`);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Creation failed.");
    } finally {
      setSaving(false);
    }
  };

  const changeStatus = async (id: string, status: string) => {
    setActionId(id);
    try {
      await patch(`/managers/cargos/${id}/status`, { status });
      notify(status === "IN_TRANSIT" ? "Convoy dispatched." : "Status updated.");
      load();
    } catch (err) {
      notify(err instanceof Error ? err.message : "Update failed.", "error");
    } finally {
      setActionId(null);
    }
  };

  return (
    <div>
      <Topbar title="Cargo Shipments" subtitle="Fleet convoy dispatch and delivery tracking" onMenu={openMobileMenu} />
      <div className="p-6">
        <div className="mb-5 flex items-center justify-between">
          <p className="text-sm text-slate-500">{cargos.length} shipment(s)</p>
          <Button onClick={handleOpenModal}>
            <PackagePlus className="h-4 w-4" /> New Shipment
          </Button>
        </div>

        {loading ? (
          <div className="flex h-40 items-center justify-center">
            <Spinner className="h-7 w-7 text-raased-teal" />
          </div>
        ) : cargos.length === 0 ? (
          <EmptyState
            icon={<Boxes className="h-8 w-8" />}
            title="No shipments"
            description="Create your first cargo shipment and dispatch the convoy."
          />
        ) : (
          <Card className="overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-slate-100 bg-slate-50/70 text-xs uppercase tracking-wide text-slate-500">
                    <th className="px-5 py-3 font-semibold">Reference</th>
                    <th className="px-5 py-3 font-semibold">Type</th>
                    <th className="px-5 py-3 font-semibold">Corridor / Route</th>
                    <th className="px-5 py-3 font-semibold">Driver</th>
                    <th className="px-5 py-3 font-semibold">Vehicle</th>
                    <th className="px-5 py-3 font-semibold">Criticality</th>
                    <th className="px-5 py-3 font-semibold">Status</th>
                    <th className="px-5 py-3 text-right font-semibold">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {cargos.map((c) => {
                    const corr = c.corridor_id ? corridorMap[c.corridor_id] : null;
                    return (
                      <tr key={c.id} className="hover:bg-slate-50/60">
                        <td className="px-5 py-3.5">
                          <p className="font-semibold text-raased-navy font-mono text-xs">{c.reference}</p>
                          {c.position && (
                            <p className="text-xs text-raased-teal">Progress {c.position.progress_pct}%</p>
                          )}
                        </td>
                        <td className="px-5 py-3.5 text-slate-500">{c.type.replace(/_/g, " ")}</td>
                        <td className="px-5 py-3.5 text-slate-600">
                          {corr ? (
                            <div>
                              <p className="font-medium text-slate-800">
                                {corr.origin} → {corr.destination}
                              </p>
                              {corr.name && corr.name !== `${corr.origin} → ${corr.destination}` && (
                                <p className="text-[11px] text-slate-400">{corr.name}</p>
                              )}
                            </div>
                          ) : c.origin && c.destination ? (
                            <span>{c.origin} → {c.destination}</span>
                          ) : (
                            <span className="text-slate-400 italic">Corridor {c.corridor_id ? c.corridor_id.slice(0, 8) : "—"}</span>
                          )}
                        </td>
                        <td className="px-5 py-3.5 text-slate-500">
                          {c.driver ? `${c.driver.first_name} ${c.driver.last_name}` : "Unassigned"}
                        </td>
                        <td className="px-5 py-3.5 text-slate-500">
                          {c.tracker?.label || c.tracker?.vehicle_registration || c.tracker?.device_id || "—"}
                        </td>
                        <td className="px-5 py-3.5">
                          <Badge value={c.criticality} />
                        </td>
                        <td className="px-5 py-3.5">
                          <Badge value={c.status} />
                        </td>
                        <td className="px-5 py-3.5">
                          <div className="flex items-center justify-end gap-2">
                            <button
                              onClick={() => handleOpenAssign(c)}
                              className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 hover:border-slate-300 transition shadow-sm"
                              title="Assign driver and vehicle"
                            >
                              <UserCheck className="h-3.5 w-3.5 text-raased-teal" /> Assign
                            </button>
                            {c.status === "PENDING" && (
                              <button
                                onClick={() => changeStatus(c.id, "IN_TRANSIT")}
                                disabled={actionId === c.id}
                                className="inline-flex items-center gap-1 rounded-lg bg-raased-teal px-2.5 py-1.5 text-xs font-semibold text-white hover:bg-raased-navy disabled:opacity-50 transition"
                              >
                                <Play className="h-3.5 w-3.5" /> Dispatch
                              </button>
                            )}
                            {c.status === "IN_TRANSIT" && (
                              <button
                                onClick={() => changeStatus(c.id, "DELIVERED")}
                                disabled={actionId === c.id}
                                className="inline-flex items-center gap-1 rounded-lg border border-emerald-200 px-2.5 py-1.5 text-xs font-semibold text-emerald-600 hover:bg-emerald-50 disabled:opacity-50 transition"
                              >
                                <Truck className="h-3.5 w-3.5" /> Delivered
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </Card>
        )}

        <Modal
          open={open}
          onClose={() => {
            setOpen(false);
            setCreatedCargo(null);
          }}
          title={createdCargo ? "Shipment Registered" : "New Shipment"}
          wide
        >
          {createdCargo ? (
            /* ── Read-only view after creation ── */
            <div className="space-y-5 py-2">
              <div className="rounded-2xl border border-emerald-500/30 bg-emerald-500/10 p-6 text-center">
                <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-emerald-500/20 text-emerald-400">
                  <CheckCircle2 className="h-6 w-6" />
                </div>
                <p className="text-xs font-semibold uppercase tracking-wider text-emerald-400">
                  Shipment created successfully
                </p>
                <div className="mt-3 inline-flex items-center gap-2 rounded-xl border border-slate-700 bg-slate-900/90 px-5 py-2.5 shadow-inner">
                  <span className="text-xs text-slate-400 font-medium">Generated Reference:</span>
                  <span className="font-mono text-xl font-extrabold text-emerald-300 tracking-wide">
                    {createdCargo.reference}
                  </span>
                </div>
                <p className="mt-2 text-xs text-slate-400">
                  This unique reference has been automatically assigned by the system.
                </p>
              </div>

              <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-4 space-y-2.5 text-sm">
                <div className="flex justify-between items-center">
                  <span className="text-slate-400">Corridor:</span>
                  <span className="font-semibold text-slate-200">{createdCargo.corridorLabel}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-slate-400">Cargo Type:</span>
                  <span className="font-semibold text-slate-200">{createdCargo.type.replace(/_/g, " ")}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-slate-400">Criticality:</span>
                  <Badge value={createdCargo.criticality} />
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-slate-400">Initial Status:</span>
                  <Badge value="PENDING" />
                </div>
                {form.tracker_id && (
                  <div className="flex justify-between items-center">
                    <span className="text-slate-400">Tracker / Vehicle:</span>
                    <span className="font-semibold text-emerald-400 text-xs">Assigned to convoy</span>
                  </div>
                )}
              </div>

              <div className="flex justify-end gap-3 pt-2">
                <Button
                  variant="outline"
                  onClick={() => {
                    setCreatedCargo(null);
                    setForm({
                      corridor_id: corridors[0]?.id || "",
                      type: "GENERAL",
                      criticality: "MEDIUM",
                      tracker_id: "",
                      driver_id: "",
                    });
                  }}
                >
                  Create another shipment
                </Button>
                <Button
                  onClick={() => {
                    setCreatedCargo(null);
                    setOpen(false);
                  }}
                >
                  Done
                </Button>
              </div>
            </div>
          ) : (
            /* ── Creation form ── */
            <div>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div className="sm:col-span-2">
                  <Select
                    label="Corridor"
                    value={form.corridor_id}
                    onChange={(e) => setForm((f) => ({ ...f, corridor_id: e.target.value }))}
                  >
                    <option value="">Select a corridor</option>
                    {corridors.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.origin} → {c.destination} {c.name && c.name !== `${c.origin} → ${c.destination}` ? `(${c.name})` : ""}
                      </option>
                    ))}
                  </Select>
                  {corridors.length === 0 && (
                    <p className="mt-1.5 text-xs text-amber-400">
                      ⚠️ No corridor configured.{" "}
                      <a href="/dashboard/corridors" className="underline font-semibold hover:text-amber-300">
                        Create a corridor first →
                      </a>
                    </p>
                  )}
                </div>

                <Select
                  label="Cargo Type"
                  value={form.type}
                  onChange={(e) => setForm((f) => ({ ...f, type: e.target.value }))}
                >
                  <option value="GENERAL">General Merchandise</option>
                  <option value="PHARMACEUTICAL">Pharmaceutical</option>
                  <option value="ELECTRONICS">Electronics</option>
                  <option value="FMCG">Consumer Goods (FMCG)</option>
                  <option value="TEXTILE">Textile</option>
                  <option value="PERISHABLE">Perishables</option>
                  <option value="HAZMAT">Hazardous Materials</option>
                </Select>

                <Select
                  label="Criticality"
                  value={form.criticality}
                  onChange={(e) => setForm((f) => ({ ...f, criticality: e.target.value }))}
                >
                  <option value="LOW">Low</option>
                  <option value="MEDIUM">Medium</option>
                  <option value="HIGH">High</option>
                  <option value="CRITICAL">Critical</option>
                </Select>

                <Select
                  label="Tracker / Vehicle"
                  value={form.tracker_id}
                  onChange={(e) => setForm((f) => ({ ...f, tracker_id: e.target.value }))}
                >
                  <option value="">Unassigned</option>
                  {trackers.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.label ? `${t.label} (${t.device_id})` : (t.vehicle_registration || t.device_id)}
                    </option>
                  ))}
                </Select>

                <Select
                  label="Driver"
                  value={form.driver_id}
                  onChange={(e) => setForm((f) => ({ ...f, driver_id: e.target.value }))}
                >
                  <option value="">Unassigned</option>
                  {drivers.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.first_name} {d.last_name}
                    </option>
                  ))}
                </Select>
              </div>

              {error && (
                <div className="mt-4 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-xs font-medium text-red-400">
                  {error}
                </div>
              )}

              <div className="mt-5 flex justify-end gap-3">
                <Button variant="outline" onClick={() => setOpen(false)}>
                  Cancel
                </Button>
                <Button loading={saving} onClick={create} disabled={!form.corridor_id}>
                  Create Shipment
                </Button>
              </div>
            </div>
          )}
        </Modal>

        {/* ── Direct Assignment Modal (Driver + Vehicle / Tracker) ── */}
        <Modal
          open={assignModalOpen}
          onClose={() => setAssignModalOpen(false)}
          title={assignCargo ? `Assign Shipment: ${assignCargo.reference}` : "Shipment Assignment"}
        >
          {assignCargo && (
            <div className="space-y-4 py-2">
              <p className="text-xs text-slate-500">
                Select the designated driver and GPS tracker vehicle for this convoy.
              </p>

              <div className="space-y-4">
                <Select
                  label="Driver"
                  value={assignForm.driver_id}
                  onChange={(e) => setAssignForm((f) => ({ ...f, driver_id: e.target.value }))}
                >
                  <option value="">Unassigned</option>
                  {drivers.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.first_name} {d.last_name} ({d.email})
                    </option>
                  ))}
                </Select>

                <Select
                  label="Vehicle / Tracker"
                  value={assignForm.tracker_id}
                  onChange={(e) => setAssignForm((f) => ({ ...f, tracker_id: e.target.value }))}
                >
                  <option value="">Unassigned</option>
                  {trackers.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.label ? `${t.label} (${t.device_id})` : (t.vehicle_registration || t.device_id)}
                    </option>
                  ))}
                </Select>
              </div>

              {assignError && (
                <div className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-xs font-medium text-red-400">
                  {assignError}
                </div>
              )}

              <div className="mt-5 flex justify-end gap-3">
                <Button variant="outline" onClick={() => setAssignModalOpen(false)}>
                  Cancel
                </Button>
                <Button loading={savingAssign} onClick={saveAssign}>
                  Save Assignment
                </Button>
              </div>
            </div>
          )}
        </Modal>
      </div>
    </div>
  );
}