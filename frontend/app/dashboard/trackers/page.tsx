"use client";

import { useEffect, useState } from "react";
import { Radio, RadioTower, Wrench } from "lucide-react";
import { Topbar } from "@/components/Topbar";
import { Badge, Button, Card, EmptyState, Input, Modal, Spinner } from "@/components/ui";
import { useShell } from "@/components/ShellContext";
import { useToast } from "@/components/Toasts";
import { get, patch, post } from "@/lib/api";

interface TrackerRow {
  id: string;
  device_id: string;
  label?: string | null;
  msisdn: string;
  status: string;
  last_seen_at?: string | null;
  created_at?: string;
}

export default function TrackersPage() {
  const { openMobileMenu } = useShell();
  const { notify } = useToast();
  const [trackers, setTrackers] = useState<TrackerRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [togglingId, setTogglingId] = useState<string | null>(null);

  // Formulaire "Nouveau tracker"
  const [form, setForm] = useState({
    label: "",
    device_id: "",
    msisdn: "",
  });

  const load = () => {
    get<any>("/managers/trackers")
      .then((d) => setTrackers(Array.isArray(d) ? d : (d?.trackers ?? [])))
      .catch(() => notify("Failed to load trackers.", "error"))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const create = async () => {
    if (!form.device_id.trim()) {
      setError("Device serial number (Device ID / IMEI) is required.");
      return;
    }
    if (!form.msisdn.trim()) {
      setError("SIM card number (MSISDN) is required for CAMARA services.");
      return;
    }

    setError("");
    setSaving(true);
    try {
      await post("/managers/trackers", {
        device_id: form.device_id.trim(),
        msisdn: form.msisdn.trim(),
        label: form.label.trim() || undefined,
      });
      notify("Tracker registered successfully.", "success");
      setOpen(false);
      setForm({ label: "", device_id: "", msisdn: "" });
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to register tracker.");
    } finally {
      setSaving(false);
    }
  };

  const toggleMaintenance = async (tracker: TrackerRow) => {
    const inMaintenance = tracker.status !== "MAINTENANCE";
    setTogglingId(tracker.id);
    try {
      await patch(`/managers/trackers/${tracker.id}/maintenance`, {
        in_maintenance: inMaintenance,
      });
      notify(
        inMaintenance
          ? `Tracker ${tracker.label || tracker.device_id} placed in maintenance.`
          : `Tracker ${tracker.label || tracker.device_id} reactivated successfully.`,
        "success"
      );
      load();
    } catch (err) {
      notify(err instanceof Error ? err.message : "Action failed.", "error");
    } finally {
      setTogglingId(null);
    }
  };

  return (
    <div>
      <Topbar title="GPS Trackers" subtitle="Fleet geolocation hardware and tracker units" onMenu={openMobileMenu} />
      <div className="p-6">
        <div className="mb-5 flex items-center justify-between">
          <p className="text-sm text-slate-500">{trackers.length} tracker(s)</p>
          <Button onClick={() => setOpen(true)}>
            <RadioTower className="h-4 w-4" /> Register Tracker
          </Button>
        </div>

        {loading ? (
          <div className="flex h-40 items-center justify-center">
            <Spinner className="h-7 w-7 text-raased-teal" />
          </div>
        ) : trackers.length === 0 ? (
          <EmptyState
            icon={<Radio className="h-8 w-8" />}
            title="No trackers"
            description="Register a GPS device to track your shipments in real time."
          />
        ) : (
          <Card className="overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-slate-100 bg-slate-50/70 text-xs uppercase tracking-wide text-slate-500">
                    <th className="px-5 py-3 font-semibold">Device Name / Unit</th>
                    <th className="px-5 py-3 font-semibold">Device ID / IMEI</th>
                    <th className="px-5 py-3 font-semibold">SIM Number (MSISDN)</th>
                    <th className="px-5 py-3 font-semibold">Status</th>
                    <th className="px-5 py-3 font-semibold">Last Activity</th>
                    <th className="px-5 py-3 text-right font-semibold">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {trackers.map((t) => (
                    <tr key={t.id} className="hover:bg-slate-50/60">
                      <td className="px-5 py-3.5">
                        {t.label ? (
                          <div>
                            <p className="font-semibold text-slate-900">{t.label}</p>
                            <p className="font-mono text-xs text-slate-400">{t.device_id}</p>
                          </div>
                        ) : (
                          <p className="font-mono text-xs font-semibold text-raased-navy">{t.device_id}</p>
                        )}
                      </td>
                      <td className="px-5 py-3.5 font-mono text-xs text-slate-600">
                        {t.device_id}
                      </td>
                      <td className="px-5 py-3.5 font-mono text-xs text-slate-600">
                        {t.msisdn || "—"}
                      </td>
                      <td className="px-5 py-3.5">
                        <Badge value={t.status} />
                      </td>
                      <td className="px-5 py-3.5 text-xs text-slate-400">
                        {t.last_seen_at
                          ? new Date(t.last_seen_at).toLocaleString("en-US")
                          : "Never"}
                      </td>
                      <td className="px-5 py-3.5 text-right">
                        {t.status === "MAINTENANCE" && (
                          <button
                            onClick={() => toggleMaintenance(t)}
                            disabled={togglingId === t.id}
                            className="inline-flex items-center gap-1 rounded-lg border border-emerald-300 bg-emerald-50 px-2.5 py-1.5 text-xs font-semibold text-emerald-700 hover:bg-emerald-100 disabled:opacity-50 transition"
                          >
                            Reactivate
                          </button>
                        )}
                        {t.status === "ACTIVE" && (
                          <button
                            onClick={() => toggleMaintenance(t)}
                            disabled={togglingId === t.id}
                            className="inline-flex items-center gap-1 rounded-lg border border-amber-300 bg-amber-50 px-2.5 py-1.5 text-xs font-semibold text-amber-700 hover:bg-amber-100 disabled:opacity-50 transition"
                          >
                            <Wrench className="h-3 w-3" /> Maintenance
                          </button>
                        )}
                        {t.status === "ASSIGNED" && (
                          <span className="text-[11px] text-slate-400 italic">
                            Assigned (in transit)
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        )}

        <Modal open={open} onClose={() => setOpen(false)} title="Register New Tracker">
          <div className="space-y-4">
            <Input
              label="Device Name (optional)"
              value={form.label}
              onChange={(e) => setForm((f) => ({ ...f, label: e.target.value }))}
              placeholder='e.g., "Renault Truck 1"'
            />
            <Input
              label="Device ID / IMEI"
              value={form.device_id}
              onChange={(e) => setForm((f) => ({ ...f, device_id: e.target.value }))}
              placeholder="Device serial number (e.g., 860123456789012)"
            />
            <div>
              <Input
                label="Line Number (MSISDN)"
                value={form.msisdn}
                onChange={(e) => setForm((f) => ({ ...f, msisdn: e.target.value }))}
                placeholder="SIM card number (e.g., +212600000000)"
              />
              <p className="mt-1 text-[11px] text-slate-400">
                Essential for CAMARA network API requests (Device Location, Quality on Demand).
              </p>
            </div>

            {error && (
              <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-medium text-red-700">
                {error}
              </div>
            )}
            <div className="flex justify-end gap-3 pt-2">
              <Button variant="outline" onClick={() => setOpen(false)}>
                Cancel
              </Button>
              <Button
                loading={saving}
                onClick={create}
                disabled={!form.device_id.trim() || !form.msisdn.trim()}
              >
                Register Tracker
              </Button>
            </div>
          </div>
        </Modal>
      </div>
    </div>
  );
}