"use client";

import { useEffect, useState } from "react";
import {
  Boxes,
  Compass,
  MapPin,
  Navigation,
  Radio,
  RefreshCw,
  ShieldCheck,
  Truck,
} from "lucide-react";
import MapView, { type LiveTrip } from "@/components/MapView";
import { Topbar } from "@/components/Topbar";
import { Badge, Button, Card, Spinner } from "@/components/ui";
import { useShell } from "@/components/ShellContext";
import { get } from "@/lib/api";

interface DriverTripPayload {
  trip?: {
    cargo: {
      id: string;
      reference: string;
      type: string;
      criticality: string;
      origin: string;
      destination: string;
      deadline?: string | null;
      vehicle_registration?: string | null;
    };
    route: [number, number][];
    position: {
      lat: number;
      lng: number;
      progress_pct: number;
      eta_minutes: number;
    } | null;
  } | null;
}

export default function DriverMapPage() {
  const { openMobileMenu } = useShell();
  const [trip, setTrip] = useState<DriverTripPayload["trip"] | null>(null);
  const [loading, setLoading] = useState(true);

  const load = () => {
    setLoading(true);
    get<DriverTripPayload>("/drivers/trip")
      .then((d) => setTrip(d.trip || null))
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
    const interval = setInterval(load, 8000);
    return () => clearInterval(interval);
  }, []);

  const liveTrips: LiveTrip[] = trip
    ? [
        {
          cargo_id: trip.cargo.id,
          reference: trip.cargo.reference,
          type: trip.cargo.type,
          criticality: trip.cargo.criticality,
          origin: trip.cargo.origin,
          destination: trip.cargo.destination,
          vehicle_registration: trip.cargo.vehicle_registration,
          driver: "Moi",
          route: trip.route,
          position: trip.position,
        },
      ]
    : [];

  return (
    <div className="flex h-screen flex-col">
      <Topbar
        title="Navigation & Convoy Map"
        subtitle="Real-time map view of your vehicle along the corridor"
        onMenu={openMobileMenu}
      />

      <div className="relative flex-1 overflow-hidden">
        {loading && !trip ? (
          <div className="flex h-full items-center justify-center bg-[#0a101d]">
            <Spinner />
          </div>
        ) : (
          <MapView
            trips={liveTrips}
            height="100%"
            zoom={10}
            fitTrip={true}
            fitRef={trip?.cargo.reference}
          />
        )}

        {/* Floating Trip Info HUD */}
        {trip && (
          <div className="absolute bottom-6 left-6 z-20 max-w-sm rounded-2xl border border-slate-800/90 bg-[#0a101d]/95 p-4 backdrop-blur shadow-2xl space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Truck className="h-5 w-5 text-blue-400" />
                <span className="font-bold text-white text-sm">{trip.cargo.reference}</span>
              </div>
              <Badge variant="success">En Route</Badge>
            </div>

            <div className="text-xs text-slate-300 space-y-1">
              <p className="flex items-center gap-1">
                <MapPin className="h-3.5 w-3.5 text-emerald-400" /> {trip.cargo.origin} → {trip.cargo.destination}
              </p>
              <p className="text-slate-400">
                Vehicle : <strong className="text-slate-200">{trip.cargo.vehicle_registration || "Truck"}</strong>
              </p>
            </div>

            {trip.position && (
              <div className="pt-2 border-t border-slate-800 flex items-center justify-between text-xs">
                <span className="text-slate-400">Progress : <strong className="text-white">{trip.position.progress_pct}%</strong></span>
                <span className="text-cyan-400 font-semibold">ETA : ~{trip.position.eta_minutes} min</span>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
