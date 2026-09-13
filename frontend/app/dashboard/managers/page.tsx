"use client";

import { useEffect, useState } from "react";
import { UserCog, UserRoundPlus } from "lucide-react";
import { Topbar } from "@/components/Topbar";
import { Badge, Button, Card, EmptyState, Input, Modal, Spinner } from "@/components/ui";
import { useShell } from "@/components/ShellContext";
import { useToast } from "@/components/Toasts";
import { get, post } from "@/lib/api";

interface ManagerRow {
  id: string;
  first_name: string;
  last_name: string;
  email: string;
  job_title?: string | null;
  account_status: string;
  current?: boolean;
}

export default function ManagersPage() {
  const { openMobileMenu } = useShell();
  const { notify } = useToast();
  const [managers, setManagers] = useState<ManagerRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [form, setForm] = useState({
    first_name: "",
    last_name: "",
    email: "",
    job_title: "",
    phone: "",
  });

  const load = () => {
    get<{ managers: ManagerRow[] }>("/managers/managers")
      .then((d) => setManagers(d.managers))
      .catch(() => notify("Failed to load managers.", "error"))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const invite = async () => {
    setError("");
    setSaving(true);
    try {
      await post("/managers/managers/invite", form);
      notify("Invitation sent to the new manager.");
      setOpen(false);
      setForm({ first_name: "", last_name: "", email: "", job_title: "", phone: "" });
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to send invitation.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div>
      <Topbar
        title="Managers"
        subtitle="Share company management with other managers"
        onMenu={openMobileMenu}
      />
      <div className="p-6">
        <div className="mb-5 flex items-center justify-between">
          <p className="text-sm text-slate-500">
            {managers.length} manager(s) in the company
          </p>
          <Button onClick={() => setOpen(true)}>
            <UserRoundPlus className="h-4 w-4" /> Invite a manager
          </Button>
        </div>

        {loading ? (
          <div className="flex h-40 items-center justify-center">
            <Spinner className="h-7 w-7 text-raased-teal" />
          </div>
        ) : managers.length === 0 ? (
          <EmptyState
            icon={<UserCog className="h-8 w-8" />}
            title="No managers"
            description="Invite a colleague to manage the fleet together."
          />
        ) : (
          <Card className="overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-slate-100 bg-slate-50/70 text-xs uppercase tracking-wide text-slate-500">
                    <th className="px-5 py-3 font-semibold">Manager</th>
                    <th className="px-5 py-3 font-semibold">Role</th>
                    <th className="px-5 py-3 font-semibold">Email</th>
                    <th className="px-5 py-3 font-semibold">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {managers.map((m) => (
                    <tr key={m.id} className="hover:bg-slate-50/60">
                      <td className="px-5 py-3.5">
                        <div className="flex items-center gap-3">
                          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-raased-navy/5 text-xs font-bold text-raased-navy">
                            {m.first_name[0]}
                            {m.last_name[0]}
                          </div>
                          <span className="font-semibold text-slate-700">
                            {m.first_name} {m.last_name}
                            {m.current && (
                              <span className="ml-2 badge bg-teal-100 text-teal-700">you</span>
                            )}
                          </span>
                        </div>
                      </td>
                      <td className="px-5 py-3.5 text-slate-500">{m.job_title || "—"}</td>
                      <td className="px-5 py-3.5 text-slate-500">{m.email}</td>
                      <td className="px-5 py-3.5">
                        {m.account_status === "INVITED" ? (
                          <Badge value="INVITED" />
                        ) : (
                          <Badge value="ACTIVE" />
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        )}

        <Modal open={open} onClose={() => setOpen(false)} title="Invite a manager">
          <div className="space-y-4">
            <p className="text-sm text-slate-500">
              The invited manager will manage the same company and receive an email to create their password.
            </p>
            <div className="grid grid-cols-2 gap-4">
              <Input
                label="First Name"
                value={form.first_name}
                onChange={(e) => setForm((f) => ({ ...f, first_name: e.target.value }))}
                placeholder="Jane"
              />
              <Input
                label="Last Name"
                value={form.last_name}
                onChange={(e) => setForm((f) => ({ ...f, last_name: e.target.value }))}
                placeholder="Doe"
              />
            </div>
            <Input
              label="Role"
              value={form.job_title}
              onChange={(e) => setForm((f) => ({ ...f, job_title: e.target.value }))}
              placeholder="Sales Director"
            />
            <Input
              label="Professional Email"
              type="email"
              value={form.email}
              onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
              placeholder="jane.doe@company.com"
            />
            <Input
              label="Phone (optional)"
              value={form.phone}
              onChange={(e) => setForm((f) => ({ ...f, phone: e.target.value }))}
              placeholder="+212 6 ..."
            />
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
                onClick={invite}
                disabled={!form.first_name || !form.last_name || !form.email}
              >
                Send invitation
              </Button>
            </div>
          </div>
        </Modal>
      </div>
    </div>
  );
}