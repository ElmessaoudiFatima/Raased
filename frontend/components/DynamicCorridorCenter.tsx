"use client";

import { useState, useEffect, useRef } from "react";
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Clock,
  FastForward,
  Gauge,
  Navigation,
  Pause,
  Play,
  Radio,
  RefreshCw,
  RotateCcw,
  ShieldAlert,
  ShieldCheck,
  Thermometer,
  Truck,
  Wifi,
  Zap,
} from "lucide-react";

interface ConvoyLive {
  id: string;
  reference: string;
  driver: string;
  origin: string;
  destination: string;
  type: string;
  criticality: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";
  progress: number;
  speed: number;
  temperature?: number;
  qodActive: boolean;
  status: "EN_ROUTE" | "DEVIATION" | "DELIVERED" | "ALERT";
  corridor: string;
  simVerified: boolean;
}

interface AgentEvent {
  id: string;
  ts: number;
  type: "QOD" | "CONGESTION" | "TRUST" | "REROUTE" | "DELIVERY";
  title: string;
  description: string;
  convoyRef: string;
  status: "AUTONOMOUS" | "PENDING_APPROVAL" | "COMPLETED";
}

const INITIAL_CONVOYS: ConvoyLive[] = [
  {
    id: "c1",
    reference: "CARGO-PHARMA-01",
    driver: "Tarik Bennani",
    origin: "Casablanca",
    destination: "Marrakech",
    type: "PHARMACEUTICAL",
    criticality: "CRITICAL",
    progress: 42,
    speed: 84,
    temperature: 4.1,
    qodActive: true,
    status: "EN_ROUTE",
    corridor: "A3 Southern Corridor",
    simVerified: true,
  },
  {
    id: "c2",
    reference: "CARGO-AGRI-04",
    driver: "Hassan Mezouar",
    origin: "Rabat",
    destination: "Tanger Med",
    type: "REFRIGERATED PRODUCE",
    criticality: "HIGH",
    progress: 68,
    speed: 79,
    temperature: 5.8,
    qodActive: false,
    status: "EN_ROUTE",
    corridor: "A1 Northern Corridor",
    simVerified: true,
  },
  {
    id: "c3",
    reference: "CARGO-INDUS-09",
    driver: "Youssef Alaoui",
    origin: "Kenitra",
    destination: "Casablanca",
    type: "AUTOMOTIVE COMPONENTS",
    criticality: "MEDIUM",
    progress: 88,
    speed: 91,
    qodActive: false,
    status: "EN_ROUTE",
    corridor: "A1 Central Axis",
    simVerified: true,
  },
  {
    id: "c4",
    reference: "CARGO-MINIER-02",
    driver: "Omar Tazi",
    origin: "Khouribga",
    destination: "Jorf Lasfar",
    type: "HEAVY FREIGHT",
    criticality: "LOW",
    progress: 25,
    speed: 62,
    qodActive: false,
    status: "EN_ROUTE",
    corridor: "R301 Western Axis",
    simVerified: true,
  },
];

const INITIAL_EVENTS: AgentEvent[] = [
  {
    id: "e1",
    ts: Date.now() - 35000,
    type: "QOD",
    title: "Quality on Demand (QoD) Activated",
    description: "High-priority CAMARA QoD session allocated for CARGO-PHARMA-01 on A3 corridor. Latency reduced to 14ms.",
    convoyRef: "CARGO-PHARMA-01",
    status: "AUTONOMOUS",
  },
  {
    id: "e2",
    ts: Date.now() - 90000,
    type: "TRUST",
    title: "SIM Swap & Device Verification Confirmed",
    description: "CAMARA Number Verification check completed: no suspicious SIM or terminal swap detected.",
    convoyRef: "CARGO-AGRI-04",
    status: "COMPLETED",
  },
];

export function DynamicCorridorCenter() {
  const [convoys, setConvoys] = useState<ConvoyLive[]>(INITIAL_CONVOYS);
  const [events, setEvents] = useState<AgentEvent[]>(INITIAL_EVENTS);
  const [isPlaying, setIsPlaying] = useState(true);
  const [simSpeed, setSimSpeed] = useState<1 | 2 | 5>(1);
  const [congestionLevel, setCongestionLevel] = useState(38);
  const [selectedConvoy, setSelectedConvoy] = useState<ConvoyLive>(INITIAL_CONVOYS[0]);
  const [activeTab, setActiveTab] = useState<"CORRIDORS" | "TELECOM" | "AGENT">("CORRIDORS");

  // Simulation clock loop
  useEffect(() => {
    if (!isPlaying) return;
    const interval = setInterval(() => {
      setConvoys((prev) =>
        prev.map((c) => {
          if (c.progress >= 100) return { ...c, progress: 100, status: "DELIVERED" };
          const increment = (c.speed / 180) * simSpeed;
          const nextProgress = Math.min(100, Number((c.progress + increment).toFixed(1)));
          // slight fluctuation in speed and temp
          const jitterSpeed = Math.max(50, Math.min(110, c.speed + (Math.random() - 0.5) * 2));
          const jitterTemp = c.temperature ? Number((c.temperature + (Math.random() - 0.49) * 0.05).toFixed(1)) : undefined;
          return {
            ...c,
            progress: nextProgress,
            speed: Math.round(jitterSpeed),
            temperature: jitterTemp,
            status: nextProgress >= 100 ? "DELIVERED" : c.status,
          };
        })
      );

      // Congestion subtle wave
      setCongestionLevel((cur) => {
        const delta = (Math.random() - 0.48) * 3;
        return Math.max(15, Math.min(95, Math.round(cur + delta)));
      });
    }, 1500);

    return () => clearInterval(interval);
  }, [isPlaying, simSpeed]);

  // Keep selected convoy fresh
  useEffect(() => {
    const updated = convoys.find((c) => c.id === selectedConvoy.id);
    if (updated) setSelectedConvoy(updated);
  }, [convoys, selectedConvoy.id]);

  // Incident Injection
  const injectIncident = (type: "CONGESTION" | "SIM_ALERT" | "TEMP_SPIKE" | "QOD_BOOST") => {
    const now = Date.now();
    if (type === "CONGESTION") {
      setCongestionLevel(88);
      const newEvent: AgentEvent = {
        id: "evt_" + now,
        ts: now,
        type: "CONGESTION",
        title: "Severe Congestion on A3 (PK-124)",
        description: "88% network cell load spike detected via CAMARA Congestion API. Convoy speed reduced by 30%.",
        convoyRef: "CARGO-PHARMA-01",
        status: "AUTONOMOUS",
      };
      setEvents((prev) => [newEvent, ...prev]);
      setConvoys((prev) =>
        prev.map((c) => (c.reference === "CARGO-PHARMA-01" ? { ...c, speed: 45, status: "ALERT" } : c))
      );
    } else if (type === "SIM_ALERT") {
      const newEvent: AgentEvent = {
        id: "evt_" + now,
        ts: now,
        type: "TRUST",
        title: "Telecom Security Alert — Suspicious SIM Swap",
        description: "Recent IMSI change detected on tracker for CARGO-AGRI-04. Operator identity check required.",
        convoyRef: "CARGO-AGRI-04",
        status: "PENDING_APPROVAL",
      };
      setEvents((prev) => [newEvent, ...prev]);
      setConvoys((prev) =>
        prev.map((c) => (c.reference === "CARGO-AGRI-04" ? { ...c, simVerified: false, status: "ALERT" } : c))
      );
    } else if (type === "TEMP_SPIKE") {
      const newEvent: AgentEvent = {
        id: "evt_" + now,
        ts: now,
        type: "CONGESTION",
        title: "Critical Cargo Temperature Spike (+7.8°C)",
        description: "Critical temperature threshold exceeded for CARGO-PHARMA-01. Priority alert dispatched to driver.",
        convoyRef: "CARGO-PHARMA-01",
        status: "AUTONOMOUS",
      };
      setEvents((prev) => [newEvent, ...prev]);
      setConvoys((prev) =>
        prev.map((c) => (c.reference === "CARGO-PHARMA-01" ? { ...c, temperature: 7.8, status: "ALERT" } : c))
      );
    } else if (type === "QOD_BOOST") {
      const newEvent: AgentEvent = {
        id: "evt_" + now,
        ts: now,
        type: "QOD",
        title: "Telecom QoD Boost Granted",
        description: "Absolute network priority assigned on cell tower. Guaranteed latency < 15ms.",
        convoyRef: selectedConvoy.reference,
        status: "COMPLETED",
      };
      setEvents((prev) => [newEvent, ...prev]);
      setConvoys((prev) =>
        prev.map((c) => (c.id === selectedConvoy.id ? { ...c, qodActive: true } : c))
      );
    }
  };

  const approveEvent = (eventId: string) => {
    setEvents((prev) =>
      prev.map((e) => (e.id === eventId ? { ...e, status: "COMPLETED" } : e))
    );
  };

  return (
    <div className="space-y-6">
      {/* Top Simulation Command Bar */}
      <div className="flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-slate-800 bg-[#0f172a]/95 p-4 shadow-xl backdrop-blur-md">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-600/20 text-blue-400 ring-1 ring-blue-500/30">
            <Activity className="h-5 w-5 animate-pulse" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/20 px-2.5 py-0.5 text-xs font-bold text-emerald-400 ring-1 ring-emerald-500/40">
                <span className="h-2 w-2 rounded-full bg-emerald-400 animate-ping" />
                Live Dynamic Supervision
              </span>
              <span className="font-mono text-xs text-slate-400">
                CAMARA Open Gateway 2026
              </span>
            </div>
            <h2 className="text-base font-bold text-white">Corridor Operations Center</h2>
          </div>
        </div>

        {/* Simulation Controls */}
        <div className="flex flex-wrap items-center gap-2.5">
          <div className="flex items-center gap-1 rounded-xl border border-slate-700/80 bg-[#0a101d] p-1">
            <button
              type="button"
              onClick={() => setIsPlaying(!isPlaying)}
              className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-bold transition ${
                isPlaying ? "bg-blue-600 text-white shadow-sm" : "bg-slate-800 text-slate-300"
              }`}
            >
              {isPlaying ? <Pause className="h-3.5 w-3.5" /> : <Play className="h-3.5 w-3.5" />}
              {isPlaying ? "Pause" : "Resume"}
            </button>
            <div className="flex items-center">
              {([1, 2, 5] as const).map((spd) => (
                <button
                  key={spd}
                  type="button"
                  onClick={() => setSimSpeed(spd)}
                  className={`rounded-lg px-2.5 py-1 text-xs font-bold transition ${
                    simSpeed === spd
                      ? "bg-blue-600/30 text-blue-400 ring-1 ring-blue-500/40"
                      : "text-slate-400 hover:text-slate-200"
                  }`}
                >
                  {spd}x
                </button>
              ))}
            </div>
          </div>

          {/* Incident Injection Dropdown */}
          <div className="flex items-center gap-1.5">
            <button
              type="button"
              onClick={() => injectIncident("CONGESTION")}
              className="rounded-xl border border-amber-500/30 bg-amber-500/10 px-3 py-1.5 text-xs font-bold text-amber-400 hover:bg-amber-500/20 transition flex items-center gap-1"
            >
              <AlertTriangle className="h-3.5 w-3.5" /> Simulate A3 Congestion
            </button>
            <button
              type="button"
              onClick={() => injectIncident("SIM_ALERT")}
              className="rounded-xl border border-red-500/30 bg-red-500/10 px-3 py-1.5 text-xs font-bold text-red-400 hover:bg-red-500/20 transition flex items-center gap-1"
            >
              <ShieldAlert className="h-3.5 w-3.5" /> Simulate SIM Swap
            </button>
            <button
              type="button"
              onClick={() => injectIncident("QOD_BOOST")}
              className="rounded-xl border border-blue-500/30 bg-blue-500/10 px-3 py-1.5 text-xs font-bold text-blue-400 hover:bg-blue-500/20 transition flex items-center gap-1"
            >
              <Zap className="h-3.5 w-3.5" /> Trigger QoD
            </button>
          </div>
        </div>
      </div>

      {/* Main Grid: Live Corridors & Convoys + Telemetry & CAMARA Panel */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Left 2 Cols: Real-Time Fleet & Corridor Trackers */}
        <div className="space-y-6 lg:col-span-2">
          {/* Convoys Live Grid */}
          <div className="rounded-2xl border border-slate-800 bg-[#0f172a]/95 p-5 shadow-xl backdrop-blur-md">
            <div className="mb-4 flex items-center justify-between">
              <div>
                <h3 className="text-sm font-bold text-white flex items-center gap-2">
                  <Truck className="h-4 w-4 text-blue-400" />
                  Fleet in Dynamic Transit ({convoys.filter((c) => c.progress < 100).length} active)
                </h3>
                <p className="text-xs text-slate-400">Click on a shipment to inspect live telemetry</p>
              </div>
              <span className="rounded-lg bg-slate-800 px-2.5 py-1 text-xs font-mono text-slate-300">
                Auto-refresh: 1.5s
              </span>
            </div>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              {convoys.map((c) => {
                const isSelected = selectedConvoy.id === c.id;
                const critBadgeColor =
                  c.criticality === "CRITICAL"
                    ? "bg-red-500/20 text-red-400 border-red-500/40"
                    : c.criticality === "HIGH"
                    ? "bg-amber-500/20 text-amber-400 border-amber-500/40"
                    : "bg-emerald-500/20 text-emerald-400 border-emerald-500/40";

                return (
                  <div
                    key={c.id}
                    onClick={() => setSelectedConvoy(c)}
                    className={`cursor-pointer rounded-xl border p-4 transition-all ${
                      isSelected
                        ? "border-blue-500 bg-blue-950/30 shadow-lg shadow-blue-500/10 ring-1 ring-blue-500/50"
                        : "border-slate-800/80 bg-[#0a101d] hover:border-slate-700"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <span className={`inline-block rounded-full border px-2 py-0.5 text-[10px] font-extrabold ${critBadgeColor}`}>
                          {c.criticality}
                        </span>
                        <h4 className="mt-1 font-bold text-white text-sm">{c.reference}</h4>
                        <p className="text-xs text-slate-400">{c.driver}</p>
                      </div>
                      <div className="text-right">
                        <span className="text-sm font-bold text-blue-400">{c.speed} km/h</span>
                        {c.temperature !== undefined && (
                          <div className={`flex items-center justify-end gap-0.5 text-xs font-mono ${c.temperature > 7 ? "text-red-400 font-bold" : "text-emerald-400"}`}>
                            <Thermometer className="h-3 w-3" /> {c.temperature}°C
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Corridor and route */}
                    <div className="mt-3 flex items-center justify-between text-xs text-slate-400">
                      <span>{c.origin} ➔ {c.destination}</span>
                      <span className="font-semibold text-slate-300">{c.progress}%</span>
                    </div>

                    {/* Progress Bar */}
                    <div className="mt-1.5 h-2 w-full overflow-hidden rounded-full bg-slate-800">
                      <div
                        className={`h-full rounded-full transition-all duration-500 ${
                          c.progress >= 100
                            ? "bg-emerald-500"
                            : c.criticality === "CRITICAL"
                            ? "bg-gradient-to-r from-blue-500 to-red-500"
                            : "bg-gradient-to-r from-blue-600 to-cyan-400"
                        }`}
                        style={{ width: `${c.progress}%` }}
                      />
                    </div>

                    {/* Footer tags */}
                    <div className="mt-3 flex items-center justify-between text-[11px]">
                      <span className="text-slate-500">{c.corridor}</span>
                      {c.qodActive && (
                        <span className="flex items-center gap-1 rounded bg-blue-600/30 px-1.5 py-0.5 text-[10px] font-bold text-blue-300">
                          <Zap className="h-3 w-3" /> QoD ACTIVE
                        </span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Detailed Telemetry for Selected Convoy */}
          <div className="rounded-2xl border border-slate-800 bg-[#0f172a]/95 p-5 shadow-xl backdrop-blur-md">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-2 border-b border-slate-800 pb-3">
              <div>
                <h3 className="text-sm font-bold text-white flex items-center gap-2">
                  <Gauge className="h-4 w-4 text-cyan-400" />
                  Live Telemetry: <span className="text-blue-400">{selectedConvoy.reference}</span>
                </h3>
                <p className="text-xs text-slate-400">Corridor {selectedConvoy.corridor} · Cargo {selectedConvoy.type}</p>
              </div>

              <div className="flex items-center gap-2">
                <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-bold ${
                  selectedConvoy.simVerified ? "bg-emerald-500/20 text-emerald-400" : "bg-red-500/20 text-red-400"
                }`}>
                  <ShieldCheck className="h-3.5 w-3.5" />
                  {selectedConvoy.simVerified ? "SIM Authenticated" : "SIM Alert"}
                </span>
                <span className="rounded-full bg-blue-600/20 px-2.5 py-1 text-xs font-bold text-blue-400">
                  Signal Quality: 94%
                </span>
              </div>
            </div>

            {/* Gauge cards */}
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
              <div className="rounded-xl border border-slate-800/80 bg-[#0a101d] p-3.5 text-center">
                <span className="text-[11px] font-semibold text-slate-400 uppercase">Current Speed</span>
                <div className="mt-1 text-2xl font-black text-white">{selectedConvoy.speed} <span className="text-xs font-normal text-slate-400">km/h</span></div>
                <div className="mt-1 text-[11px] text-emerald-400">Stable speed</div>
              </div>

              <div className="rounded-xl border border-slate-800/80 bg-[#0a101d] p-3.5 text-center">
                <span className="text-[11px] font-semibold text-slate-400 uppercase">Progress</span>
                <div className="mt-1 text-2xl font-black text-blue-400">{selectedConvoy.progress}%</div>
                <div className="mt-1 text-[11px] text-slate-400">ETA ~{Math.round((100 - selectedConvoy.progress) * 1.8)} min</div>
              </div>

              <div className="rounded-xl border border-slate-800/80 bg-[#0a101d] p-3.5 text-center">
                <span className="text-[11px] font-semibold text-slate-400 uppercase">Cargo Temperature</span>
                <div className={`mt-1 text-2xl font-black ${selectedConvoy.temperature && selectedConvoy.temperature > 7 ? "text-red-400" : "text-emerald-400"}`}>
                  {selectedConvoy.temperature !== undefined ? `${selectedConvoy.temperature}°C` : "Ambient"}
                </div>
                <div className="mt-1 text-[11px] text-slate-400">Setpoint: +2°C to +8°C</div>
              </div>

              <div className="rounded-xl border border-slate-800/80 bg-[#0a101d] p-3.5 text-center">
                <span className="text-[11px] font-semibold text-slate-400 uppercase">Network Latency</span>
                <div className="mt-1 text-2xl font-black text-cyan-400">{selectedConvoy.qodActive ? "14 ms" : "78 ms"}</div>
                <div className="mt-1 text-[11px] text-blue-400">{selectedConvoy.qodActive ? "QoD Active" : "Standard 4G/5G"}</div>
              </div>
            </div>
          </div>
        </div>

        {/* Right Col: CAMARA Telecom Intelligence & Live Agent Event Feed */}
        <div className="space-y-6">
          {/* CAMARA API Intelligence Panel */}
          <div className="rounded-2xl border border-slate-800 bg-[#0f172a]/95 p-5 shadow-xl backdrop-blur-md">
            <div className="mb-4 flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                <Wifi className="h-4 w-4 text-blue-400" />
                CAMARA Telecom Intelligence
              </h3>
              <span className="rounded bg-blue-950/60 px-2 py-0.5 text-[10px] font-mono text-blue-400 border border-blue-500/30">
                Nokia / GSMA
              </span>
            </div>

            {/* Congestion Gauge */}
            <div className="rounded-xl border border-slate-800/80 bg-[#0a101d] p-4">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-300">Network Congestion Index (A3)</span>
                <span className={`text-sm font-extrabold ${congestionLevel > 70 ? "text-red-400" : "text-emerald-400"}`}>
                  {congestionLevel}%
                </span>
              </div>
              <div className="mt-2 h-2.5 w-full overflow-hidden rounded-full bg-slate-800">
                <div
                  className={`h-full rounded-full transition-all duration-700 ${
                    congestionLevel > 70
                      ? "bg-gradient-to-r from-amber-500 to-red-500"
                      : "bg-gradient-to-r from-emerald-500 to-blue-500"
                  }`}
                  style={{ width: `${congestionLevel}%` }}
                />
              </div>
              <p className="mt-2 text-[11px] text-slate-400">
                {congestionLevel > 70
                  ? "Alert: High network cell density detected. Raased Agent operating in preventive reroute mode."
                  : "Smooth traffic flow. No radio tower disruptions detected."}
              </p>
            </div>

            {/* Trust Checks List */}
            <div className="mt-4 space-y-2 text-xs">
              <div className="flex items-center justify-between rounded-lg border border-slate-800 bg-[#0a101d] p-2.5">
                <span className="text-slate-300 flex items-center gap-1.5">
                  <ShieldCheck className="h-3.5 w-3.5 text-emerald-400" /> Number Verification
                </span>
                <span className="font-bold text-emerald-400">AUTHENTICATED</span>
              </div>
              <div className="flex items-center justify-between rounded-lg border border-slate-800 bg-[#0a101d] p-2.5">
                <span className="text-slate-300 flex items-center gap-1.5">
                  <ShieldCheck className="h-3.5 w-3.5 text-emerald-400" /> SIM Swap Check
                </span>
                <span className="font-bold text-emerald-400">SECURED (0d)</span>
              </div>
              <div className="flex items-center justify-between rounded-lg border border-slate-800 bg-[#0a101d] p-2.5">
                <span className="text-slate-300 flex items-center gap-1.5">
                  <ShieldCheck className="h-3.5 w-3.5 text-emerald-400" /> Quality on Demand
                </span>
                <span className="font-bold text-blue-400">AVAILABLE</span>
              </div>
            </div>
          </div>

          {/* Live Agent Action Feed */}
          <div className="rounded-2xl border border-slate-800 bg-[#0f172a]/95 p-5 shadow-xl backdrop-blur-md">
            <div className="mb-4 flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                <Zap className="h-4 w-4 text-amber-400" />
                AI Agent Action Log
              </h3>
              <span className="text-[10px] font-mono text-slate-400">Append-only audit</span>
            </div>

            <div className="max-h-[380px] space-y-3 overflow-y-auto pr-1">
              {events.map((e) => (
                <div
                  key={e.id}
                  className="rounded-xl border border-slate-800 bg-[#0a101d] p-3.5 transition hover:border-slate-700"
                >
                  <div className="flex items-start justify-between gap-2">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-blue-400">
                      {e.type} · {e.convoyRef}
                    </span>
                    <span className="text-[10px] text-slate-500 font-mono">
                      {new Date(e.ts).toLocaleTimeString("en-US")}
                    </span>
                  </div>
                  <h4 className="mt-1 font-bold text-white text-xs">{e.title}</h4>
                  <p className="mt-1 text-[11px] text-slate-400 leading-relaxed">{e.description}</p>

                  <div className="mt-3 flex items-center justify-between">
                    <span
                      className={`inline-block rounded px-2 py-0.5 text-[10px] font-bold ${
                        e.status === "AUTONOMOUS"
                          ? "bg-blue-500/20 text-blue-400"
                          : e.status === "PENDING_APPROVAL"
                          ? "bg-amber-500/20 text-amber-400"
                          : "bg-emerald-500/20 text-emerald-400"
                      }`}
                    >
                      {e.status === "AUTONOMOUS"
                        ? "Autonomous Action"
                        : e.status === "PENDING_APPROVAL"
                        ? "Approval Required"
                        : "Executed"}
                    </span>

                    {e.status === "PENDING_APPROVAL" && (
                      <button
                        type="button"
                        onClick={() => approveEvent(e.id)}
                        className="rounded-lg bg-blue-600 px-2.5 py-1 text-[11px] font-bold text-white hover:bg-blue-500 transition"
                      >
                        Approve
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default DynamicCorridorCenter;
