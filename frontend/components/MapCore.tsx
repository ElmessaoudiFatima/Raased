"use client";

import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import type { MapViewProps } from "./MapView";
import { Layers, Maximize2, Navigation, Radio, Sparkles } from "lucide-react";

const TRUCK_ICON = `
<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
  <path d="M14 18V6a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2v11a1 1 0 0 0 1 1h2"/>
  <path d="M15 18H9"/>
  <path d="M19 18h2a1 1 0 0 0 1-1v-3.65a1 1 0 0 0-.22-.62l-3.48-4.35a1 1 0 0 0-.78-.38H14"/>
  <circle cx="7" cy="18" r="2"/>
  <circle cx="17" cy="18" r="2"/>
</svg>`;

const criticalityColor: Record<string, string> = {
  LOW: "#10b981",
  MEDIUM: "#f59e0b",
  HIGH: "#f97316",
  CRITICAL: "#ef4444",
};

const riskColor: Record<string, string> = {
  LOW: "rgba(16, 185, 129, 0.18)",
  MEDIUM: "rgba(245, 158, 11, 0.22)",
  HIGH: "rgba(239, 68, 68, 0.28)",
};

function truckIcon(color: string, ref: string) {
  return L.divIcon({
    className: "",
    html: `
      <div style="position:relative;display:flex;align-items:center;justify-content:center;width:38px;height:38px;border-radius:50%;background:${color};border:3px solid white;box-shadow:0 4px 14px rgba(0,0,0,0.45);transform:translate(-2px,-2px);animation:pulse-marker 2.5s infinite">
        ${TRUCK_ICON}
      </div>
    `,
    iconSize: [38, 38],
    iconAnchor: [19, 19],
    popupAnchor: [0, -20],
  });
}

const startIcon = L.divIcon({
  className: "",
  html: `<div style="width:16px;height:16px;border-radius:50%;background:#10b981;border:3px solid white;box-shadow:0 2px 8px rgba(0,0,0,0.4)"></div>`,
  iconSize: [16, 16],
  iconAnchor: [8, 8],
});

const endIcon = L.divIcon({
  className: "",
  html: `<div style="width:16px;height:16px;border-radius:50%;background:#ef4444;border:3px solid white;box-shadow:0 2px 8px rgba(0,0,0,0.4)"></div>`,
  iconSize: [16, 16],
  iconAnchor: [8, 8],
});

// Google Maps Tile URLs
const GOOGLE_MAPS_TILES = {
  roadmap: "https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}",
  satellite: "https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
  hybrid: "https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}",
  terrain: "https://mt1.google.com/vt/lyrs=p&x={x}&y={y}&z={z}",
};

type MapType = "roadmap" | "hybrid" | "terrain";

let lastFit: string | null = null;

export default function MapCore({
  trips,
  corridors = [],
  riskZones = [],
  height = "100%",
  zoom = 7,
  fitTrip = false,
  fitRef = null,
  onTripFocus,
}: MapViewProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const tileLayerRef = useRef<L.TileLayer | null>(null);
  const layerRef = useRef<L.LayerGroup | null>(null);
  const [mapType, setMapType] = useState<MapType>("roadmap");
  const [showTraffic, setShowTraffic] = useState(true);

  // Initialize Map with Google Maps Roadmap by default
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const map = L.map(containerRef.current, {
      zoomControl: false, // We render custom Google Maps style zoom controls
      attributionControl: false,
    }).setView([31.79, -7.09], zoom);

    const tileLayer = L.tileLayer(GOOGLE_MAPS_TILES.roadmap, {
      maxZoom: 20,
      subdomains: ["mt0", "mt1", "mt2", "mt3"],
    }).addTo(map);

    tileLayerRef.current = tileLayer;
    layerRef.current = L.layerGroup().addTo(map);
    mapRef.current = map;

    return () => {
      map.remove();
      mapRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Handle Map Type change (Roadmap, Satellite Hybrid, Terrain)
  const changeMapType = (type: MapType) => {
    setMapType(type);
    if (tileLayerRef.current && mapRef.current) {
      tileLayerRef.current.setUrl(GOOGLE_MAPS_TILES[type]);
    }
  };

  // Zoom helpers
  const handleZoomIn = () => mapRef.current?.zoomIn();
  const handleZoomOut = () => mapRef.current?.zoomOut();
  const handleRecenter = () => {
    if (!mapRef.current) return;
    if (trips.length > 0 && trips.some((t) => t.position)) {
      const validPoints = trips
        .filter((t) => t.position)
        .map((t) => [t.position!.lat, t.position!.lng] as [number, number]);
      if (validPoints.length > 0) {
        mapRef.current.fitBounds(L.latLngBounds(validPoints), { padding: [60, 60], maxZoom: 11 });
        return;
      }
    }
    mapRef.current.setView([31.79, -7.09], 7);
  };

  useEffect(() => {
    const map = mapRef.current;
    const layer = layerRef.current;
    if (!map || !layer) return;
    layer.clearLayers();

    // Risk zones
    for (const z of riskZones) {
      if (!z.points || z.points.length < 3) continue;
      L.polygon(z.points as L.LatLngExpression[], {
        color: z.risk_level === "HIGH" ? "#ef4444" : z.risk_level === "MEDIUM" ? "#f59e0b" : "#10b981",
        weight: 2,
        fillColor: riskColor[z.risk_level] || "rgba(239,68,68,0.2)",
        fillOpacity: 1,
        dashArray: "6 4",
      })
        .bindPopup(
          `<div style="font-family:inherit;min-width:200px;padding:4px">
            <div style="font-size:11px;font-weight:700;text-transform:uppercase;color:#ef4444;margin-bottom:2px">Zone à risque — ${z.risk_level}</div>
            <p style="font-weight:700;font-size:14px;color:#0f172a;margin:0 0 4px">${z.name}</p>
            <p style="margin:0;font-size:12px;color:#64748b">Type : ${z.type.toLowerCase()} · Corridor sous vigilance</p>
          </div>`
        )
        .addTo(layer);
    }

    // Corridors
    for (const c of corridors) {
      if (!c.points || c.points.length < 2) continue;
      L.polyline(c.points as L.LatLngExpression[], {
        color: showTraffic ? "#3b82f6" : "#64748b",
        weight: showTraffic ? 5 : 3,
        opacity: showTraffic ? 0.85 : 0.6,
        dashArray: showTraffic ? undefined : "3 6",
      })
        .bindPopup(
          `<div style="font-family:inherit;min-width:180px;padding:4px">
            <div style="font-size:11px;font-weight:700;color:#2563eb;text-transform:uppercase">Corridor Logistique</div>
            <p style="font-weight:700;font-size:13px;color:#0f172a;margin:2px 0 0">${c.name}</p>
          </div>`
        )
        .addTo(layer);
    }

    // Active Trips
    for (const t of trips) {
      const color = criticalityColor[t.criticality] || "#2563eb";
      if (t.route && t.route.length > 1) {
        L.polyline(t.route as L.LatLngExpression[], {
          color,
          weight: 4,
          opacity: 0.9,
        }).addTo(layer);
      }
      if (t.route && t.route.length > 0) {
        L.marker(t.route[0] as L.LatLngExpression, { icon: startIcon }).addTo(layer);
        L.marker(t.route[t.route.length - 1] as L.LatLngExpression, { icon: endIcon }).addTo(layer);
      }
      if (t.position) {
        const popup = `
          <div style="font-family:inherit;min-width:220px;padding:6px 4px">
            <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:6px">
              <span style="font-size:10px;font-weight:800;letter-spacing:.5px;padding:2px 8px;border-radius:9999px;background:${color}20;color:${color};border:1px solid ${color}40">
                ${t.criticality}
              </span>
              <span style="font-size:11px;font-weight:600;color:#64748b">
                ${t.vehicle_registration || "Camion"}
              </span>
            </div>
            <p style="font-weight:800;font-size:15px;color:#0f172a;margin:0 0 2px">
              ${t.reference || "Convoi"}
            </p>
            <p style="font-size:12px;color:#475569;margin:0 0 8px">
              📍 ${t.origin} ➔ ${t.destination}
            </p>
            <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:8px;font-size:12px">
              <div style="display:flex;justify-content:space-between;margin-bottom:4px">
                <span style="color:#64748b">Chauffeur:</span>
                <span style="font-weight:600;color:#1e293b">${t.driver || "Non assigné"}</span>
              </div>
              <div style="display:flex;justify-content:space-between;margin-bottom:4px">
                <span style="color:#64748b">Progression:</span>
                <span style="font-weight:700;color:#2563eb">${t.position.progress_pct}%</span>
              </div>
              <div style="display:flex;justify-content:space-between">
                <span style="color:#64748b">ETA estimé:</span>
                <span style="font-weight:700;color:#10b981">~${t.position.eta_minutes} min</span>
              </div>
            </div>
          </div>`;

        const marker = L.marker([t.position.lat, t.position.lng], {
          icon: truckIcon(color, t.reference),
          zIndexOffset: 1000,
        })
          .bindPopup(popup)
          .addTo(layer);

        if (onTripFocus) {
          marker.on("click", () => onTripFocus(t.reference));
        }
      }
    }
  }, [trips, corridors, riskZones, onTripFocus, showTraffic]);

  useEffect(() => {
    if (!fitTrip || !fitRef) return;
    const map = mapRef.current;
    if (!map) return;
    const trip = trips.find((t) => t.reference === fitRef);
    if (!trip || !trip.route?.length) return;
    if (lastFit === fitRef) return;
    lastFit = fitRef;
    map.flyToBounds(L.latLngBounds(trip.route as L.LatLngExpression[]), {
      padding: [50, 50],
      maxZoom: 12,
    });
  }, [fitTrip, fitRef, trips]);

  return (
    <div className="relative h-full w-full overflow-hidden">
      {/* Google Maps Styled Floating Controls */}
      <div className="absolute top-3 left-3 z-[1000] flex items-center gap-1.5 rounded-xl bg-white/95 p-1 shadow-lg backdrop-blur ring-1 ring-black/10">
        <button
          type="button"
          onClick={() => changeMapType("roadmap")}
          className={`rounded-lg px-3 py-1.5 text-xs font-bold transition-all ${
            mapType === "roadmap"
              ? "bg-blue-600 text-white shadow-sm"
              : "text-slate-700 hover:bg-slate-100"
          }`}
        >
          Plan (Google)
        </button>
        <button
          type="button"
          onClick={() => changeMapType("hybrid")}
          className={`rounded-lg px-3 py-1.5 text-xs font-bold transition-all ${
            mapType === "hybrid"
              ? "bg-blue-600 text-white shadow-sm"
              : "text-slate-700 hover:bg-slate-100"
          }`}
        >
          Satellite
        </button>
        <button
          type="button"
          onClick={() => changeMapType("terrain")}
          className={`rounded-lg px-3 py-1.5 text-xs font-bold transition-all ${
            mapType === "terrain"
              ? "bg-blue-600 text-white shadow-sm"
              : "text-slate-700 hover:bg-slate-100"
          }`}
        >
          Relief
        </button>
      </div>

      {/* Traffic Toggle Button (Google Maps Style) */}
      <div className="absolute top-3 right-3 z-[1000] flex items-center gap-2">
        <button
          type="button"
          onClick={() => setShowTraffic(!showTraffic)}
          className={`flex items-center gap-1.5 rounded-xl px-3 py-2 text-xs font-bold shadow-lg backdrop-blur transition-all ring-1 ring-black/10 ${
            showTraffic
              ? "bg-emerald-600 text-white shadow-emerald-600/20"
              : "bg-white/95 text-slate-700 hover:bg-slate-100"
          }`}
        >
          <Radio className="h-3.5 w-3.5" />
          {showTraffic ? "Trafic & Corridors ON" : "Trafic OFF"}
        </button>
      </div>

      {/* Custom Google Maps Style Zoom & Recenter Controls (Bottom Right) */}
      <div className="absolute bottom-6 right-3 z-[1000] flex flex-col gap-1.5">
        <button
          type="button"
          onClick={handleRecenter}
          title="Centrer sur la flotte"
          className="flex h-10 w-10 items-center justify-center rounded-xl bg-white/95 text-slate-700 shadow-lg ring-1 ring-black/10 hover:bg-slate-50 transition active:scale-95"
        >
          <Navigation className="h-4 w-4 text-blue-600" />
        </button>
        <div className="flex flex-col overflow-hidden rounded-xl bg-white/95 shadow-lg ring-1 ring-black/10">
          <button
            type="button"
            onClick={handleZoomIn}
            className="flex h-10 w-10 items-center justify-center border-b border-slate-200 text-lg font-bold text-slate-700 hover:bg-slate-50 transition active:scale-95"
          >
            +
          </button>
          <button
            type="button"
            onClick={handleZoomOut}
            className="flex h-10 w-10 items-center justify-center text-lg font-bold text-slate-700 hover:bg-slate-50 transition active:scale-95"
          >
            −
          </button>
        </div>
      </div>

      {/* Map Canvas */}
      <div ref={containerRef} style={{ height, width: "100%" }} className="z-0" />
    </div>
  );
}
