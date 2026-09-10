"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { Loader2, RotateCcw, MapPin, Flag } from "lucide-react";

export interface CorridorGeometry {
  type: "LineString";
  coordinates: [number, number][];
}

export interface CorridorItem {
  id: string;
  name: string;
  origin: string;
  destination: string;
  risk_level: string;
  is_active: boolean;
  geometry?: CorridorGeometry | null;
}

export interface CorridorMapProps {
  corridors: CorridorItem[];
  drawMode?: boolean;
  onRouteChange?: (geo: CorridorGeometry | null) => void;
  highlightId?: string | null;
}

const RISK_COLORS: Record<string, string> = {
  LOW: "#10b981",
  MEDIUM: "#f59e0b",
  HIGH: "#f97316",
  CRITICAL: "#ef4444",
};

const GOOGLE_TILES = {
  roadmap: "https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}",
  hybrid: "https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}",
};

async function geocode(query: string): Promise<{ label: string; lat: number; lon: number }[]> {
  const url = `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(query)}&limit=5&addressdetails=1`;
  const res = await fetch(url, { headers: { "Accept-Language": "fr" } });
  const data = await res.json();
  return data.map((r: any) => ({
    label: r.display_name,
    lat: parseFloat(r.lat),
    lon: parseFloat(r.lon),
  }));
}

async function getRoute(waypoints: [number, number][]): Promise<[number, number][] | null> {
  if (waypoints.length < 2) return null;
  const coords = waypoints.map(([lat, lon]) => `${lon},${lat}`).join(";");
  const url = `https://router.project-osrm.org/route/v1/driving/${coords}?overview=full&geometries=geojson`;
  try {
    const res = await fetch(url);
    const data = await res.json();
    if (data.code !== "Ok" || !data.routes[0]) return null;
    return data.routes[0].geometry.coordinates.map(([lon, lat]: [number, number]) => [lat, lon]);
  } catch {
    return null;
  }
}

function useNominatim(query: string) {
  const [results, setResults] = useState<{ label: string; lat: number; lon: number }[]>([]);
  const [loading, setLoading] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!query || query.length < 3) { setResults([]); return; }
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(async () => {
      setLoading(true);
      try { setResults(await geocode(query)); }
      catch { setResults([]); }
      finally { setLoading(false); }
    }, 350);
    return () => { if (timerRef.current) clearTimeout(timerRef.current); };
  }, [query]);

  return { results, loading };
}

export default function CorridorMap({ corridors, drawMode = false, onRouteChange, highlightId }: CorridorMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const corridorLayerRef = useRef<L.LayerGroup | null>(null);
  const drawLayerRef = useRef<L.LayerGroup | null>(null);

  const [originQuery, setOriginQuery] = useState("");
  const [destQuery, setDestQuery] = useState("");
  const [originPt, setOriginPt] = useState<{ label: string; lat: number; lon: number } | null>(null);
  const [destPt, setDestPt] = useState<{ label: string; lat: number; lon: number } | null>(null);
  const [waypoints, setWaypoints] = useState<[number, number][]>([]);
  const [routing, setRouting] = useState(false);
  const [showOriginDrop, setShowOriginDrop] = useState(false);
  const [showDestDrop, setShowDestDrop] = useState(false);
  const [mapType, setMapType] = useState<"roadmap" | "hybrid">("roadmap");
  const tileRef = useRef<L.TileLayer | null>(null);

  const { results: originResults, loading: originLoading } = useNominatim(originQuery);
  const { results: destResults, loading: destLoading } = useNominatim(destQuery);

  // Init map
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const map = L.map(containerRef.current, { zoomControl: false, attributionControl: false })
      .setView([31.79, -7.09], 6);
    tileRef.current = L.tileLayer(GOOGLE_TILES.roadmap, { maxZoom: 20 }).addTo(map);
    corridorLayerRef.current = L.layerGroup().addTo(map);
    drawLayerRef.current = L.layerGroup().addTo(map);
    L.control.zoom({ position: "bottomright" }).addTo(map);
    mapRef.current = map;
    return () => { map.remove(); mapRef.current = null; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (tileRef.current) tileRef.current.setUrl(GOOGLE_TILES[mapType]);
  }, [mapType]);

  // Render existing corridors
  useEffect(() => {
    const layer = corridorLayerRef.current;
    if (!layer) return;
    layer.clearLayers();
    for (const c of corridors) {
      if (!c.geometry?.coordinates || c.geometry.coordinates.length < 2) continue;
      const isHL = c.id === highlightId;
      const color = RISK_COLORS[c.risk_level] || "#3b82f6";
      const pts: L.LatLngExpression[] = c.geometry.coordinates.map(([lon, lat]) => [lat, lon]);
      L.polyline(pts, {
        color: isHL ? "#2563eb" : color,
        weight: isHL ? 7 : 4,
        opacity: isHL ? 1 : 0.75,
        dashArray: c.is_active ? undefined : "8 6",
      })
        .bindPopup(
          `<div style="font-family:system-ui;min-width:180px;padding:4px">
            <div style="font-size:11px;font-weight:700;text-transform:uppercase;color:${color};margin-bottom:2px">Corridor — ${c.risk_level}</div>
            <p style="font-weight:700;font-size:14px;color:#0f172a;margin:0 0 4px">${c.name}</p>
            <p style="margin:0;font-size:12px;color:#64748b">📍 ${c.origin} → ${c.destination}</p>
          </div>`
        )
        .addTo(layer);
    }
  }, [corridors, highlightId]);

  const computeRoute = useCallback(async (origin: typeof originPt, dest: typeof destPt) => {
    if (!origin || !dest) return;
    setRouting(true);
    const pts = await getRoute([[origin.lat, origin.lon], [dest.lat, dest.lon]]);
    setRouting(false);
    if (pts) setWaypoints(pts);
  }, []);

  // Draw route
  useEffect(() => {
    const layer = drawLayerRef.current;
    if (!layer) return;
    layer.clearLayers();

    if (waypoints.length < 2) { onRouteChange?.(null); return; }

    const poly = L.polyline(waypoints as L.LatLngExpression[], {
      color: "#2563eb", weight: 5, opacity: 0.9, dashArray: "10 6",
    }).addTo(layer);

    const startIcon = L.divIcon({
      className: "",
      html: `<div style="width:14px;height:14px;border-radius:50%;background:#10b981;border:3px solid white;box-shadow:0 2px 8px rgba(0,0,0,.4)"></div>`,
      iconSize: [14, 14], iconAnchor: [7, 7],
    });
    const endIcon = L.divIcon({
      className: "",
      html: `<div style="width:14px;height:14px;border-radius:50%;background:#ef4444;border:3px solid white;box-shadow:0 2px 8px rgba(0,0,0,.4)"></div>`,
      iconSize: [14, 14], iconAnchor: [7, 7],
    });
    L.marker(waypoints[0] as L.LatLngExpression, { icon: startIcon }).bindTooltip("Départ").addTo(layer);
    L.marker(waypoints[waypoints.length - 1] as L.LatLngExpression, { icon: endIcon }).bindTooltip("Arrivée").addTo(layer);

    // Draggable intermediate handles
    const stride = Math.max(1, Math.floor(waypoints.length / 8));
    const handleIndices: number[] = [];
    for (let i = stride; i < waypoints.length - stride; i += stride) handleIndices.push(i);

    for (const idx of handleIndices) {
      const hIcon = L.divIcon({
        className: "",
        html: `<div style="width:12px;height:12px;border-radius:50%;background:#2563eb;border:2px solid white;box-shadow:0 1px 4px rgba(0,0,0,.4);cursor:grab"></div>`,
        iconSize: [12, 12], iconAnchor: [6, 6],
      });
      const marker = L.marker(waypoints[idx] as L.LatLngExpression, { icon: hIcon, draggable: true, zIndexOffset: 500 }).addTo(layer);
      marker.on("dragend", async () => {
        const pos = marker.getLatLng();
        const prevIdx = handleIndices[handleIndices.indexOf(idx) - 1] ?? 0;
        const nextIdx = handleIndices[handleIndices.indexOf(idx) + 1] ?? waypoints.length - 1;
        const segment = await getRoute([waypoints[prevIdx], [pos.lat, pos.lng], waypoints[nextIdx]]);
        if (segment) {
          const newWps = [...waypoints];
          newWps.splice(prevIdx, nextIdx - prevIdx + 1, ...segment);
          setWaypoints(newWps);
        }
      });
    }

    mapRef.current?.fitBounds(poly.getBounds(), { padding: [50, 50], maxZoom: 11 });

    // GeoJSON uses [lon, lat]
    const coords: [number, number][] = waypoints.map(([lat, lon]) => [lon, lat]);
    onRouteChange?.({ type: "LineString", coordinates: coords });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [waypoints]);

  const handleSelectOrigin = (r: typeof originResults[0]) => {
    setOriginPt(r);
    setOriginQuery(r.label.split(",")[0]);
    setShowOriginDrop(false);
    computeRoute(r, destPt);
  };

  const handleSelectDest = (r: typeof destResults[0]) => {
    setDestPt(r);
    setDestQuery(r.label.split(",")[0]);
    setShowDestDrop(false);
    computeRoute(originPt, r);
  };

  const handleReset = () => {
    setOriginQuery(""); setDestQuery(""); setOriginPt(null); setDestPt(null); setWaypoints([]);
    onRouteChange?.(null);
  };

  return (
    <div className="relative h-full w-full overflow-hidden">
      <div ref={containerRef} style={{ height: "100%", width: "100%" }} className="z-0" />

      {/* Map type toggle */}
      <div className="absolute top-3 left-3 z-[1000] flex items-center gap-1 rounded-xl bg-white/95 p-1 shadow-lg ring-1 ring-black/10 backdrop-blur">
        {(["roadmap", "hybrid"] as const).map((t) => (
          <button key={t} type="button" onClick={() => setMapType(t)}
            className={`rounded-lg px-3 py-1.5 text-xs font-bold transition-all ${mapType === t ? "bg-blue-600 text-white shadow-sm" : "text-slate-700 hover:bg-slate-100"}`}>
            {t === "roadmap" ? "Plan" : "Satellite"}
          </button>
        ))}
      </div>

      {/* Draw mode controls */}
      {drawMode && (
        <div className="absolute top-3 right-3 z-[1000] flex flex-col gap-2" style={{ width: 280 }}>
          {/* Origin */}
          <div className="relative">
            <div className="flex items-center gap-2 rounded-xl bg-white/97 px-3 py-2.5 shadow-lg ring-1 ring-black/10 backdrop-blur">
              <MapPin className="h-4 w-4 shrink-0 text-emerald-500" />
              <input
                className="flex-1 bg-transparent text-sm outline-none placeholder:text-slate-400 text-slate-800"
                placeholder="Ville d'origine…"
                value={originQuery}
                onChange={(e) => { setOriginQuery(e.target.value); setShowOriginDrop(true); }}
                onFocus={() => setShowOriginDrop(true)}
                onBlur={() => setTimeout(() => setShowOriginDrop(false), 150)}
              />
              {originLoading && <Loader2 className="h-3.5 w-3.5 animate-spin text-slate-400" />}
            </div>
            {showOriginDrop && originResults.length > 0 && (
              <div className="absolute top-full mt-1 w-full rounded-xl bg-white shadow-xl ring-1 ring-black/10 overflow-hidden z-20 max-h-48 overflow-y-auto">
                {originResults.map((r, i) => (
                  <button key={i} type="button"
                    className="block w-full px-3 py-2 text-left text-xs text-slate-700 hover:bg-blue-50 border-b border-slate-100 last:border-0 transition"
                    onMouseDown={() => handleSelectOrigin(r)}>
                    <span className="font-semibold">{r.label.split(",")[0]}</span>
                    <span className="text-slate-400 ml-1 truncate">{r.label.split(",").slice(1, 3).join(",")}</span>
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Destination */}
          <div className="relative">
            <div className="flex items-center gap-2 rounded-xl bg-white/97 px-3 py-2.5 shadow-lg ring-1 ring-black/10 backdrop-blur">
              <Flag className="h-4 w-4 shrink-0 text-red-500" />
              <input
                className="flex-1 bg-transparent text-sm outline-none placeholder:text-slate-400 text-slate-800"
                placeholder="Ville de destination…"
                value={destQuery}
                onChange={(e) => { setDestQuery(e.target.value); setShowDestDrop(true); }}
                onFocus={() => setShowDestDrop(true)}
                onBlur={() => setTimeout(() => setShowDestDrop(false), 150)}
              />
              {destLoading && <Loader2 className="h-3.5 w-3.5 animate-spin text-slate-400" />}
            </div>
            {showDestDrop && destResults.length > 0 && (
              <div className="absolute top-full mt-1 w-full rounded-xl bg-white shadow-xl ring-1 ring-black/10 overflow-hidden z-20 max-h-48 overflow-y-auto">
                {destResults.map((r, i) => (
                  <button key={i} type="button"
                    className="block w-full px-3 py-2 text-left text-xs text-slate-700 hover:bg-blue-50 border-b border-slate-100 last:border-0 transition"
                    onMouseDown={() => handleSelectDest(r)}>
                    <span className="font-semibold">{r.label.split(",")[0]}</span>
                    <span className="text-slate-400 ml-1 truncate">{r.label.split(",").slice(1, 3).join(",")}</span>
                  </button>
                ))}
              </div>
            )}
          </div>

          {routing && (
            <div className="flex items-center gap-2 rounded-xl bg-blue-600/90 px-3 py-2 text-xs font-semibold text-white shadow-lg backdrop-blur">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              Calcul de l'itinéraire OSRM…
            </div>
          )}

          {(originPt || destPt) && !routing && (
            <button type="button" onClick={handleReset}
              className="flex items-center gap-2 rounded-xl bg-white/95 px-3 py-2 text-xs font-semibold text-slate-600 shadow-lg ring-1 ring-black/10 backdrop-blur hover:bg-red-50 hover:text-red-600 transition">
              <RotateCcw className="h-3.5 w-3.5" />
              Réinitialiser le tracé
            </button>
          )}
        </div>
      )}
    </div>
  );
}
