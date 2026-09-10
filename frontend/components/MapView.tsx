"use client";

import dynamic from "next/dynamic";

export interface LiveTrip {
  cargo_id: string;
  reference: string;
  type: string;
  criticality: string;
  origin: string;
  destination: string;
  vehicle_registration?: string | null;
  driver?: string | null;
  route: [number, number][];
  position: { lat: number; lng: number; progress_pct: number; eta_minutes: number } | null;
}

export interface CorridorShape {
  id: string;
  name: string;
  risk_level: string;
  points: [number, number][];
}

export interface RiskZoneShape {
  id: string;
  name: string;
  type: string;
  risk_level: string;
  points: [number, number][];
}

export interface MapViewProps {
  trips: LiveTrip[];
  corridors?: CorridorShape[];
  riskZones?: RiskZoneShape[];
  height?: string;
  zoom?: number;
  fitTrip?: boolean;
  fitRef?: string | null;
  onTripFocus?: (ref: string) => void;
}

const MapCore = dynamic(import("@/components/MapCore"), {
  ssr: false,
  loading: () => (
    <div className="flex h-full w-full items-center justify-center bg-slate-100 text-sm text-slate-500">
      Chargement de la carte…
    </div>
  ),
});

export default function MapView(props: MapViewProps) {
  return <MapCore {...props} />;
}