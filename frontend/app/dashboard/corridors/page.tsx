"use client";

import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import {
  Building2,
  Plus,
  Pencil,
  Trash2,
  CheckCircle2,
  XCircle,
  ArrowRight,
  ArrowLeft,
  Route,
  Save,
  X,
  ShieldAlert,
  Cloud,
  Wind,
  Thermometer,
  AlertTriangle,
} from "lucide-react";
import { Topbar } from "@/components/Topbar";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  Input,
  Select,
  Textarea,
  Spinner,
} from "@/components/ui";
import { useShell } from "@/components/ShellContext";
import { useToast } from "@/components/Toasts";
import { get, post, patch, del } from "@/lib/api";
import type {
  CorridorGeometry,
  CorridorItem,
  RiskZoneItem,
  RiskZoneGeometry,
} from "@/components/CorridorMap";

// Dynamic import — no SSR for Leaflet
const CorridorMap = dynamic(() => import("@/components/CorridorMap"), {
  ssr: false,
  loading: () => (
    <div className="flex h-full w-full items-center justify-center bg-slate-100 text-sm text-slate-500 rounded-2xl">
      Chargement de la carte…
    </div>
  ),
});

const RISK_LEVELS = ["LOW", "MEDIUM", "HIGH", "CRITICAL"] as const;
type RiskLevel = (typeof RISK_LEVELS)[number];

const RISK_COLORS: Record<RiskLevel, string> = {
  LOW: "text-emerald-600 bg-emerald-50 border-emerald-200",
  MEDIUM: "text-amber-600 bg-amber-50 border-amber-200",
  HIGH: "text-orange-600 bg-orange-50 border-orange-200",
  CRITICAL: "text-red-600 bg-red-50 border-red-200",
};

const RISK_DOT: Record<RiskLevel, string> = {
  LOW: "bg-emerald-500",
  MEDIUM: "bg-amber-500",
  HIGH: "bg-orange-500",
  CRITICAL: "bg-red-500",
};

const ZONE_TYPES = [
  "ACCIDENT",
  "FLOOD",
  "ROADBLOCK",
  "CRIME",
  "CONSTRUCTION",
  "CUSTOMS_CONTROL",
  "OTHER",
] as const;

type Mode = "list" | "create" | "edit" | "zones";

interface CorridorForm {
  name: string;
  risk_level: RiskLevel;
}

interface ZoneForm {
  name: string;
  type: string;
  risk_level: RiskLevel;
  description: string;
}

interface WeatherData {
  temperature_c?: number | null;
  wind_speed_kmh?: number | null;
  weather_code?: number | null;
  degraded_conditions?: boolean | null;
  recorded_at?: string | null;
  from_cache?: boolean;
}

export default function CorridorsPage() {
  const { openMobileMenu } = useShell();
  const { notify } = useToast();

  const [corridors, setCorridors] = useState<CorridorItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [mode, setMode] = useState<Mode>("list");
  const [highlightId, setHighlightId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState<string | null>(null);

  // Create / edit form state
  const [form, setForm] = useState<CorridorForm>({
    name: "",
    risk_level: "LOW",
  });
  const [currentGeo, setCurrentGeo] = useState<CorridorGeometry | null>(null);
  const [editId, setEditId] = useState<string | null>(null);
  const [geoError, setGeoError] = useState("");

  // ─── Risk zones state ───
  const [zonesCorridor, setZonesCorridor] = useState<CorridorItem | null>(null);
  const [zones, setZones] = useState<RiskZoneItem[]>([]);
  const [zonesLoading, setZonesLoading] = useState(false);
  const [addingZone, setAddingZone] = useState(false);
  const [zoneForm, setZoneForm] = useState<ZoneForm>({
    name: "",
    type: "ACCIDENT",
    risk_level: "MEDIUM",
    description: "",
  });
  const [zoneDraftGeometry, setZoneDraftGeometry] =
    useState<RiskZoneGeometry | null>(null);
  const [zoneDraftSignal, setZoneDraftSignal] = useState(0);
  const [zoneSaving, setZoneSaving] = useState(false);
  const [zoneDeleting, setZoneDeleting] = useState<string | null>(null);
  const [weather, setWeather] = useState<WeatherData | null>(null);
  const [weatherLoading, setWeatherLoading] = useState(false);

  // --- Data fetching ---
  const load = () => {
    get<any>("/managers/corridors")
      .then((d) => setCorridors(Array.isArray(d) ? d : (d?.corridors ?? [])))
      .catch(() => notify("Impossible de charger les corridors.", "error"))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const loadZones = (corridorId: string) => {
    setZonesLoading(true);
    get<any>(`/managers/corridors/${corridorId}/zones`)
      .then((d) => setZones(Array.isArray(d) ? d : (d?.zones ?? [])))
      .catch(() => notify("Impossible de charger les zones à risque.", "error"))
      .finally(() => setZonesLoading(false));
  };

  const loadWeather = (corridorId: string) => {
    setWeatherLoading(true);
    setWeather(null);
    get<WeatherData>(`/managers/corridors/${corridorId}/weather`)
      .then((d) => setWeather(d))
      .catch(() => setWeather(null))
      .finally(() => setWeatherLoading(false));
  };

  // --- Corridor handlers ---
  const handleCreate = () => {
    setForm({ name: "", risk_level: "LOW" });
    setCurrentGeo(null);
    setEditId(null);
    setGeoError("");
    setMode("create");
  };

  const handleEdit = (c: CorridorItem) => {
    setForm({ name: c.name, risk_level: c.risk_level as RiskLevel });
    setCurrentGeo(c.geometry ?? null);
    setEditId(c.id);
    setGeoError("");
    setMode("edit");
    setHighlightId(c.id);
  };

  const handleCancel = () => {
    setMode("list");
    setEditId(null);
    setHighlightId(null);
    setCurrentGeo(null);
    setGeoError("");
  };

  const handleSave = async () => {
    if (!form.name.trim()) {
      notify("Le nom du corridor est requis.", "error");
      return;
    }
    if (!currentGeo || currentGeo.coordinates.length < 2) {
      setGeoError("Tracez un itinéraire sur la carte avant d'enregistrer.");
      return;
    }
    setGeoError("");
    setSaving(true);

    try {
      if (mode === "create") {
        const originCoord = currentGeo.coordinates[0];
        const destCoord =
          currentGeo.coordinates[currentGeo.coordinates.length - 1];
        const originLabel = await reverseGeocode(
          originCoord[1],
          originCoord[0],
        );
        const destLabel = await reverseGeocode(destCoord[1], destCoord[0]);

        await post("/managers/corridors", {
          name: form.name,
          origin: originLabel,
          destination: destLabel,
          risk_level: form.risk_level,
          geometry: currentGeo,
        });
        notify("Corridor créé avec succès !", "success");
      } else if (mode === "edit" && editId) {
        await patch(`/managers/corridors/${editId}`, {
          name: form.name,
          risk_level: form.risk_level,
          geometry: currentGeo,
        });
        notify("Corridor mis à jour.", "success");
      }
      handleCancel();
      load();
    } catch (err) {
      notify(
        err instanceof Error ? err.message : "Erreur lors de l'enregistrement.",
        "error",
      );
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Supprimer ce corridor ? Cette action est irréversible."))
      return;
    setDeleting(id);
    try {
      await del(`/managers/corridors/${id}`);
      notify("Corridor supprimé.", "success");
      if (highlightId === id) handleCancel();
      load();
    } catch (err) {
      notify(
        err instanceof Error ? err.message : "Erreur lors de la suppression.",
        "error",
      );
    } finally {
      setDeleting(null);
    }
  };

  // --- Risk zone handlers ---
  const handleManageZones = (c: CorridorItem) => {
    setZonesCorridor(c);
    setMode("zones");
    setHighlightId(c.id);
    setAddingZone(false);
    setZoneForm({
      name: "",
      type: "ACCIDENT",
      risk_level: "MEDIUM",
      description: "",
    });
    setZoneDraftGeometry(null);
    loadZones(c.id);
    loadWeather(c.id);
  };

  const handleExitZones = () => {
    setMode("list");
    setZonesCorridor(null);
    setZones([]);
    setHighlightId(null);
    setAddingZone(false);
    setZoneDraftGeometry(null);
    setWeather(null);
  };

  const handleStartAddZone = () => {
    setAddingZone(true);
    setZoneForm({
      name: "",
      type: "ACCIDENT",
      risk_level: "MEDIUM",
      description: "",
    });
    setZoneDraftGeometry(null);
    setZoneDraftSignal((n) => n + 1);
  };

  const handleCancelAddZone = () => {
    setAddingZone(false);
    setZoneDraftGeometry(null);
    setZoneDraftSignal((n) => n + 1);
  };

  const handleSaveZone = async () => {
    if (!zonesCorridor) return;
    if (!zoneForm.name.trim()) {
      notify("Le nom de la zone est requis.", "error");
      return;
    }
    if (!zoneDraftGeometry) {
      notify("Cliquez sur la carte pour placer le centre de la zone.", "error");
      return;
    }
    setZoneSaving(true);
    try {
      await post(`/managers/corridors/${zonesCorridor.id}/zones`, {
        name: zoneForm.name,
        type: zoneForm.type,
        risk_level: zoneForm.risk_level,
        description: zoneForm.description || undefined,
        geometry: zoneDraftGeometry,
      });
      notify("Zone à risque créée.", "success");
      setAddingZone(false);
      setZoneDraftGeometry(null);
      setZoneDraftSignal((n) => n + 1);
      loadZones(zonesCorridor.id);
    } catch (err) {
      notify(
        err instanceof Error
          ? err.message
          : "Erreur lors de la création de la zone.",
        "error",
      );
    } finally {
      setZoneSaving(false);
    }
  };

  const handleDeleteZone = async (zoneId: string) => {
    if (!confirm("Supprimer cette zone à risque ?")) return;
    setZoneDeleting(zoneId);
    try {
      await del(`/managers/zones/${zoneId}`);
      notify("Zone supprimée.", "success");
      if (zonesCorridor) loadZones(zonesCorridor.id);
    } catch (err) {
      notify(
        err instanceof Error ? err.message : "Erreur lors de la suppression.",
        "error",
      );
    } finally {
      setZoneDeleting(null);
    }
  };

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-[#060d1a]">
      <Topbar
        title="Corridors logistiques"
        subtitle="Tracez et gérez vos corridors de transport"
        onMenu={openMobileMenu}
      />

      <div className="flex flex-1 overflow-hidden gap-0">
        {/* ───────────── Left panel ───────────── */}
        <div className="flex w-[380px] shrink-0 flex-col border-r border-slate-800/60 overflow-hidden">
          {mode === "zones" && zonesCorridor ? (
            <ZonesPanel
              corridor={zonesCorridor}
              zones={zones}
              loading={zonesLoading}
              addingZone={addingZone}
              zoneForm={zoneForm}
              setZoneForm={setZoneForm}
              zoneDraftGeometry={zoneDraftGeometry}
              zoneSaving={zoneSaving}
              zoneDeleting={zoneDeleting}
              weather={weather}
              weatherLoading={weatherLoading}
              onBack={handleExitZones}
              onStartAdd={handleStartAddZone}
              onCancelAdd={handleCancelAddZone}
              onSave={handleSaveZone}
              onDelete={handleDeleteZone}
            />
          ) : (
            <>
              {/* Header */}
              <div className="flex items-center justify-between px-5 py-4 border-b border-slate-800/60">
                <div>
                  <p className="text-sm font-bold text-slate-100">
                    {corridors.length} corridor
                    {corridors.length !== 1 ? "s" : ""}
                  </p>
                  <p className="text-xs text-slate-500 mt-0.5">
                    Actifs et globaux
                  </p>
                </div>
                {mode === "list" && (
                  <Button size="sm" onClick={handleCreate} className="gap-1.5">
                    <Plus className="h-3.5 w-3.5" />
                    Nouveau
                  </Button>
                )}
              </div>

              {/* Form (create / edit) */}
              {(mode === "create" || mode === "edit") && (
                <div className="border-b border-slate-800/60 bg-slate-900/40 px-5 py-4 space-y-3">
                  <p className="text-xs font-bold text-slate-300 uppercase tracking-wider">
                    {mode === "create"
                      ? "Nouveau corridor"
                      : "Modifier le corridor"}
                  </p>
                  <Input
                    label="Nom du corridor"
                    dark
                    placeholder="Ex: Casablanca → Marrakech (A7)"
                    value={form.name}
                    onChange={(e) =>
                      setForm((f) => ({ ...f, name: e.target.value }))
                    }
                  />
                  <Select
                    label="Niveau de risque"
                    dark
                    value={form.risk_level}
                    onChange={(e) =>
                      setForm((f) => ({
                        ...f,
                        risk_level: e.target.value as RiskLevel,
                      }))
                    }
                  >
                    {RISK_LEVELS.map((r) => (
                      <option key={r} value={r}>
                        {r}
                      </option>
                    ))}
                  </Select>

                  {geoError && (
                    <p className="text-xs font-medium text-red-400 flex items-center gap-1.5">
                      <XCircle className="h-3.5 w-3.5 shrink-0" />
                      {geoError}
                    </p>
                  )}

                  {currentGeo && (
                    <p className="text-xs text-emerald-400 flex items-center gap-1.5">
                      <CheckCircle2 className="h-3.5 w-3.5 shrink-0" />
                      Tracé prêt — {currentGeo.coordinates.length} points
                    </p>
                  )}

                  <div className="flex gap-2 pt-1">
                    <Button
                      loading={saving}
                      onClick={handleSave}
                      className="flex-1 gap-1.5"
                      disabled={!form.name || !currentGeo}
                    >
                      <Save className="h-3.5 w-3.5" />
                      Enregistrer
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={handleCancel}
                      className="gap-1.5"
                    >
                      <X className="h-3.5 w-3.5" />
                      Annuler
                    </Button>
                  </div>

                  <p className="text-xs text-slate-500 leading-relaxed">
                    💡 Utilisez les champs sur la carte (haut à droite) pour
                    tracer l'itinéraire. Déplacez les points bleus pour ajuster
                    le tracé.
                  </p>
                </div>
              )}

              {/* Corridor list */}
              <div className="flex-1 overflow-y-auto p-4 space-y-2">
                {loading ? (
                  <div className="flex h-32 items-center justify-center">
                    <Spinner className="h-6 w-6 text-blue-500" />
                  </div>
                ) : corridors.length === 0 ? (
                  <EmptyState
                    icon={<Route className="h-8 w-8" />}
                    title="Aucun corridor"
                    description="Créez votre premier corridor logistique en cliquant sur « Nouveau »."
                  />
                ) : (
                  corridors.map((c) => (
                    <CorridorCard
                      key={c.id}
                      corridor={c}
                      isHighlighted={highlightId === c.id}
                      isDeleting={deleting === c.id}
                      onMouseEnter={() => setHighlightId(c.id)}
                      onMouseLeave={() =>
                        mode === "list" && setHighlightId(null)
                      }
                      onEdit={() => handleEdit(c)}
                      onDelete={() => handleDelete(c.id)}
                      onManageZones={() => handleManageZones(c)}
                      isOwned={!!c.organization_id}
                    />
                  ))
                )}
              </div>
            </>
          )}
        </div>

        {/* ───────────── Right panel (map) ───────────── */}
        <div className="flex-1 overflow-hidden p-4">
          <div className="h-full w-full rounded-2xl overflow-hidden shadow-2xl ring-1 ring-slate-800/60">
            <CorridorMap
              corridors={corridors}
              drawMode={mode === "create" || mode === "edit"}
              onRouteChange={setCurrentGeo}
              highlightId={highlightId}
              zones={mode === "zones" ? zones : []}
              zoneDrawMode={mode === "zones" && addingZone}
              onZoneGeometryChange={setZoneDraftGeometry}
              clearZoneDraftSignal={zoneDraftSignal}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Sub-component: Zones management panel ───

function ZonesPanel({
  corridor,
  zones,
  loading,
  addingZone,
  zoneForm,
  setZoneForm,
  zoneDraftGeometry,
  zoneSaving,
  zoneDeleting,
  weather,
  weatherLoading,
  onBack,
  onStartAdd,
  onCancelAdd,
  onSave,
  onDelete,
}: {
  corridor: CorridorItem;
  zones: RiskZoneItem[];
  loading: boolean;
  addingZone: boolean;
  zoneForm: ZoneForm;
  setZoneForm: React.Dispatch<React.SetStateAction<ZoneForm>>;
  zoneDraftGeometry: RiskZoneGeometry | null;
  zoneSaving: boolean;
  zoneDeleting: string | null;
  weather: WeatherData | null;
  weatherLoading: boolean;
  onBack: () => void;
  onStartAdd: () => void;
  onCancelAdd: () => void;
  onSave: () => void;
  onDelete: (id: string) => void;
}) {
  return (
    <div className="flex flex-1 flex-col overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-2 px-5 py-4 border-b border-slate-800/60">
        <button
          type="button"
          onClick={onBack}
          className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-800 hover:text-white transition"
        >
          <ArrowLeft className="h-4 w-4" />
        </button>
        <div className="min-w-0">
          <p className="text-sm font-bold text-slate-100 truncate">
            Zones — {corridor.name}
          </p>
          <p className="text-xs text-slate-500 mt-0.5 truncate">
            {corridor.origin} → {corridor.destination}
          </p>
        </div>
      </div>

      {/* Weather panel (informational only) */}
      <div className="px-5 py-3 border-b border-slate-800/60 bg-slate-900/40">
        {weatherLoading ? (
          <div className="flex items-center gap-2 text-xs text-slate-500">
            <Spinner className="h-3.5 w-3.5" /> Chargement météo…
          </div>
        ) : weather ? (
          <div className="flex items-center justify-between text-xs">
            <div className="flex items-center gap-3">
              <span className="flex items-center gap-1 text-slate-300">
                <Thermometer className="h-3.5 w-3.5 text-orange-400" />
                {weather.temperature_c != null
                  ? `${Math.round(weather.temperature_c)}°C`
                  : "—"}
              </span>
              <span className="flex items-center gap-1 text-slate-300">
                <Wind className="h-3.5 w-3.5 text-sky-400" />
                {weather.wind_speed_kmh != null
                  ? `${Math.round(weather.wind_speed_kmh)} km/h`
                  : "—"}
              </span>
            </div>
            {weather.degraded_conditions && (
              <span className="flex items-center gap-1 text-amber-400 font-semibold">
                <AlertTriangle className="h-3.5 w-3.5" /> Conditions dégradées
              </span>
            )}
          </div>
        ) : (
          <p className="flex items-center gap-1.5 text-xs text-slate-500">
            <Cloud className="h-3.5 w-3.5" /> Météo indisponible pour ce
            corridor.
          </p>
        )}
        <p className="mt-1.5 text-[10px] text-slate-600 leading-relaxed">
          💡 Information indicative pour ce corridor — ne remplace pas votre
          connaissance opérationnelle du terrain (zone d'accident connue,
          contrôle douanier, historique local…).
        </p>
      </div>

      {/* Add zone form */}
      {addingZone ? (
        <div className="border-b border-slate-800/60 bg-slate-900/40 px-5 py-4 space-y-3">
          <p className="text-xs font-bold text-slate-300 uppercase tracking-wider">
            Nouvelle zone à risque
          </p>
          <Input
            label="Nom"
            dark
            placeholder="Ex: Zone de régulation poids lourds"
            value={zoneForm.name}
            onChange={(e) =>
              setZoneForm((f) => ({ ...f, name: e.target.value }))
            }
          />
          <Select
            label="Type"
            dark
            value={zoneForm.type}
            onChange={(e) =>
              setZoneForm((f) => ({ ...f, type: e.target.value }))
            }
          >
            {ZONE_TYPES.map((t) => (
              <option key={t} value={t}>
                {t.replace(/_/g, " ")}
              </option>
            ))}
          </Select>
          <Select
            label="Niveau de risque"
            dark
            value={zoneForm.risk_level}
            onChange={(e) =>
              setZoneForm((f) => ({
                ...f,
                risk_level: e.target.value as RiskLevel,
              }))
            }
          >
            {RISK_LEVELS.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </Select>
          <Textarea
            label="Description (optionnel)"
            dark
            placeholder="Contexte opérationnel, précisions…"
            value={zoneForm.description}
            onChange={(e) =>
              setZoneForm((f) => ({ ...f, description: e.target.value }))
            }
          />

          {zoneDraftGeometry ? (
            <p className="text-xs text-emerald-400 flex items-center gap-1.5">
              <CheckCircle2 className="h-3.5 w-3.5 shrink-0" />
              Cercle placé sur la carte
            </p>
          ) : (
            <p className="text-xs text-amber-400 flex items-center gap-1.5">
              <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
              Cliquez sur la carte pour placer la zone
            </p>
          )}

          <div className="flex gap-2 pt-1">
            <Button
              loading={zoneSaving}
              onClick={onSave}
              className="flex-1 gap-1.5"
              disabled={!zoneForm.name || !zoneDraftGeometry}
            >
              <Save className="h-3.5 w-3.5" />
              Enregistrer
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={onCancelAdd}
              className="gap-1.5"
            >
              <X className="h-3.5 w-3.5" />
              Annuler
            </Button>
          </div>
        </div>
      ) : (
        <div className="px-5 py-3 border-b border-slate-800/60">
          <Button size="sm" onClick={onStartAdd} className="w-full gap-1.5">
            <Plus className="h-3.5 w-3.5" />
            Nouvelle zone à risque
          </Button>
        </div>
      )}

      {/* Zones list */}
      <div className="flex-1 overflow-y-auto p-4 space-y-2">
        {loading ? (
          <div className="flex h-32 items-center justify-center">
            <Spinner className="h-6 w-6 text-blue-500" />
          </div>
        ) : zones.length === 0 ? (
          <EmptyState
            icon={<ShieldAlert className="h-8 w-8" />}
            title="Aucune zone à risque"
            description="Ajoutez une zone à risque sur ce corridor pour renforcer la surveillance."
          />
        ) : (
          zones.map((z) => {
            const riskKey = z.risk_level as RiskLevel;
            return (
              <div
                key={z.id}
                className="group relative rounded-2xl border border-slate-800/60 bg-slate-900/40 p-4 hover:border-slate-700 hover:bg-slate-900/70 transition-all"
              >
                <div className="flex items-start justify-between gap-2 mb-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <div
                      className={`h-2.5 w-2.5 rounded-full shrink-0 ${RISK_DOT[riskKey] ?? "bg-slate-500"}`}
                    />
                    <p className="text-sm font-bold text-slate-100 truncate">
                      {z.name}
                    </p>
                  </div>
                  <span
                    className={`shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase ${RISK_COLORS[riskKey] ?? ""}`}
                  >
                    {z.risk_level}
                  </span>
                </div>
                <p className="text-xs text-slate-400 mb-1">
                  {z.type.replace(/_/g, " ")}
                </p>
                {z.description && (
                  <p className="text-xs text-slate-500 mb-2 line-clamp-2">
                    {z.description}
                  </p>
                )}
                <div className="flex items-center justify-between">
                  {z.is_active ? (
                    <span className="flex items-center gap-1 text-[10px] font-semibold text-emerald-400">
                      <CheckCircle2 className="h-3 w-3" /> Active
                    </span>
                  ) : (
                    <span className="flex items-center gap-1 text-[10px] font-semibold text-slate-500">
                      <XCircle className="h-3 w-3" /> Inactive
                    </span>
                  )}
                  <button
                    type="button"
                    onClick={() => onDelete(z.id)}
                    disabled={zoneDeleting === z.id}
                    className="rounded-lg p-1.5 text-slate-400 opacity-0 group-hover:opacity-100 hover:bg-red-900/40 hover:text-red-400 transition disabled:opacity-50"
                  >
                    {zoneDeleting === z.id ? (
                      <Spinner className="h-3.5 w-3.5" />
                    ) : (
                      <Trash2 className="h-3.5 w-3.5" />
                    )}
                  </button>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}

// ─── Sub-component: Corridor card ───

function CorridorCard({
  corridor: c,
  isHighlighted,
  isDeleting,
  onMouseEnter,
  onMouseLeave,
  onEdit,
  onDelete,
  onManageZones,
  isOwned,
}: {
  corridor: CorridorItem;
  isHighlighted: boolean;
  isDeleting: boolean;
  onMouseEnter: () => void;
  onMouseLeave: () => void;
  onEdit: () => void;
  onDelete: () => void;
  onManageZones: () => void;
  isOwned: boolean;
}) {
  const riskKey = c.risk_level as RiskLevel;
  return (
    <div
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
      className={`group relative rounded-2xl border p-4 transition-all duration-200 cursor-pointer ${
        isHighlighted
          ? "border-blue-500/50 bg-blue-500/10 shadow-lg shadow-blue-900/20"
          : "border-slate-800/60 bg-slate-900/40 hover:border-slate-700 hover:bg-slate-900/70"
      }`}
    >
      {/* Top row */}
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="flex items-center gap-2 min-w-0">
          <div
            className={`h-2.5 w-2.5 rounded-full shrink-0 ${RISK_DOT[riskKey] ?? "bg-slate-500"}`}
          />
          <p className="text-sm font-bold text-slate-100 truncate">{c.name}</p>
        </div>
        <span
          className={`shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase ${RISK_COLORS[riskKey] ?? ""}`}
        >
          {c.risk_level}
        </span>
      </div>

      {/* Route */}
      <div className="flex items-center gap-1.5 text-xs text-slate-400 mb-3">
        <span className="truncate max-w-[110px]">{c.origin}</span>
        <ArrowRight className="h-3 w-3 shrink-0 text-slate-600" />
        <span className="truncate max-w-[110px]">{c.destination}</span>
      </div>

      {!isOwned && (
        <p className="text-[10px] text-slate-500 italic mb-2">
          Corridor global — lecture seule
        </p>
      )}

      {/* Bottom row */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {c.is_active ? (
            <span className="flex items-center gap-1 text-[10px] font-semibold text-emerald-400">
              <CheckCircle2 className="h-3 w-3" /> Actif
            </span>
          ) : (
            <span className="flex items-center gap-1 text-[10px] font-semibold text-slate-500">
              <XCircle className="h-3 w-3" /> Inactif
            </span>
          )}
          {!c.geometry && (
            <span className="text-[10px] text-slate-500 italic">
              Sans tracé
            </span>
          )}
        </div>

        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
          {isOwned && (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onManageZones();
              }}
              title="Zones à risque"
              className="rounded-lg p-1.5 text-slate-400 hover:bg-purple-900/40 hover:text-purple-300 transition"
            >
              <ShieldAlert className="h-3.5 w-3.5" />
            </button>
          )}
          {isOwned && (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onEdit();
              }}
              title="Modifier"
              className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-700 hover:text-blue-300 transition"
            >
              <Pencil className="h-3.5 w-3.5" />
            </button>
          )}
          {isOwned && (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onDelete();
              }}
              title="Supprimer"
              disabled={isDeleting}
              className="rounded-lg p-1.5 text-slate-400 hover:bg-red-900/40 hover:text-red-400 transition disabled:opacity-50"
            >
              {isDeleting ? (
                <Spinner className="h-3.5 w-3.5" />
              ) : (
                <Trash2 className="h-3.5 w-3.5" />
              )}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

// Reverse geocode a [lat, lon] point to a human-readable city name
async function reverseGeocode(lat: number, lon: number): Promise<string> {
  try {
    const url = `https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lon}&zoom=10`;
    const res = await fetch(url, { headers: { "Accept-Language": "fr" } });
    const data = await res.json();
    return (
      data.address?.city ||
      data.address?.town ||
      data.address?.village ||
      data.address?.county ||
      data.display_name?.split(",")[0] ||
      `${lat.toFixed(3)}, ${lon.toFixed(3)}`
    );
  } catch {
    return `${lat.toFixed(3)}, ${lon.toFixed(3)}`;
  }
}
