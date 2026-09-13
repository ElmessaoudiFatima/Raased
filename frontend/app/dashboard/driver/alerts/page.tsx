"use client";

import { useEffect, useState } from "react";
import {
  AlertTriangle,
  Bot,
  CheckCircle2,
  Clock,
  Compass,
  Navigation,
  RefreshCw,
  ShieldAlert,
  Sparkles,
  Zap,
} from "lucide-react";
import { Topbar } from "@/components/Topbar";
import { Badge, Button, Card, EmptyState, Spinner } from "@/components/ui";
import { useShell } from "@/components/ShellContext";
import { useToast } from "@/components/Toasts";
import { get, patch } from "@/lib/api";

interface DriverAlert {
  id: string;
  severity: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
  title: string;
  message: string;
  status: string;
  created_at?: string | null;
  cargo_reference?: string | null;
}

export default function DriverAlertsPage() {
  const { openMobileMenu } = useShell();
  const { notify } = useToast();

  const [alerts, setAlerts] = useState<DriverAlert[]>([]);
  const [loading, setLoading] = useState(true);
  const [ackId, setAckId] = useState<string | null>(null);

  const load = () => {
    setLoading(true);
    get<{ alerts: DriverAlert[] }>("/drivers/alerts")
      .then((d) => setAlerts(d.alerts))
      .catch(() => notify("Failed to load alerts.", "error"))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const acknowledge = async (id: string) => {
    setAckId(id);
    try {
      await patch(`/drivers/alerts/${id}/acknowledge`);
      notify("Alert acknowledged by driver.");
      setAlerts((prev) =>
        prev.map((a) => (a.id === id ? { ...a, status: "ACKNOWLEDGED" } : a))
      );
    } catch (err) {
      notify(err instanceof Error ? err.message : "Validation error.", "error");
    } finally {
      setAckId(null);
    }
  };

  const getSeverityBadge = (sev: string) => {
    switch (sev) {
      case "CRITICAL":
        return "bg-red-500/20 text-red-300 border-red-500/30";
      case "HIGH":
        return "bg-amber-500/20 text-amber-300 border-amber-500/30";
      case "MEDIUM":
        return "bg-yellow-500/20 text-yellow-300 border-yellow-500/30";
      default:
        return "bg-blue-500/20 text-blue-300 border-blue-500/30";
    }
  };

  return (
    <div>
      <Topbar
        title="Alerts & AI Directives"
        subtitle="Critical notifications, route conditions, and driving recommendations"
        onMenu={openMobileMenu}
      />

      <div className="p-6 space-y-6">
        <div className="flex items-center justify-between">
          <p className="text-sm text-slate-400">
            {alerts.length} alert(s) listed for your convoy
          </p>
          <Button variant="outline" size="sm" onClick={load} loading={loading}>
            <RefreshCw className="h-3.5 w-3.5 mr-1" /> Refresh
          </Button>
        </div>

        {/* AI Copilot Suggestion Card */}
        <Card className="p-5 border-blue-500/30 bg-blue-950/20 space-y-3">
          <div className="flex items-center gap-2.5 text-blue-300">
            <Sparkles className="h-5 w-5 text-amber-400" />
            <h3 className="font-bold text-sm">Raased AI Copilot — Active Recommendation</h3>
          </div>
          <p className="text-xs text-slate-300 leading-relaxed">
            "Significant slowdown reported near Settat. The CAMARA QoD profile has been automatically boosted to ensure continuous telematics link. Follow the recommended route on your map to save 22 minutes."
          </p>
        </Card>

        {/* Alerts List */}
        {loading ? (
          <div className="flex h-64 items-center justify-center">
            <Spinner />
          </div>
        ) : alerts.length === 0 ? (
          <Card className="p-8 border-slate-800 bg-[#0f172a]">
            <EmptyState
              icon={<CheckCircle2 className="h-10 w-10 text-emerald-400" />}
              title="No anomalies reported"
              description="Your convoy is progressing under nominal safety and schedule conditions."
            />
          </Card>
        ) : (
          <div className="space-y-3">
            {alerts.map((a) => (
              <Card
                key={a.id}
                className="p-5 border-slate-800 bg-[#0f172a] hover:border-slate-700 transition space-y-3 shadow-lg"
              >
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-slate-900 border border-slate-800">
                      <AlertTriangle className="h-5 w-5 text-amber-400" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <h4 className="font-bold text-white text-sm">{a.title}</h4>
                        <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-bold border ${getSeverityBadge(a.severity)}`}>
                          {a.severity}
                        </span>
                      </div>
                      {a.cargo_reference && (
                        <p className="text-xs text-slate-400 mt-0.5">
                          Affected cargo: <strong className="text-slate-200">{a.cargo_reference}</strong>
                        </p>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-3 self-end sm:self-center">
                    {a.status === "ACKNOWLEDGED" ? (
                      <span className="inline-flex items-center gap-1 rounded-lg bg-emerald-500/10 px-2.5 py-1 text-xs font-semibold text-emerald-400 border border-emerald-500/20">
                        <CheckCircle2 className="h-3.5 w-3.5" /> Acknowledged
                      </span>
                    ) : (
                      <Button
                        variant="figma"
                        size="sm"
                        loading={ackId === a.id}
                        onClick={() => acknowledge(a.id)}
                        className="text-xs"
                      >
                        Acknowledge alert
                      </Button>
                    )}
                  </div>
                </div>

                <p className="text-xs text-slate-300 leading-relaxed bg-[#0a101d] p-3 rounded-xl border border-slate-800">
                  {a.message}
                </p>

                {a.created_at && (
                  <p className="text-[11px] text-slate-500 flex items-center gap-1">
                    <Clock className="h-3 w-3" /> Received on {new Date(a.created_at).toLocaleString("en-US")}
                  </p>
                )}
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
