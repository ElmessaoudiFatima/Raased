"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  Activity,
  AlertTriangle,
  Boxes,
  Building2,
  FileCheck2,
  LayoutGrid,
  LogOut,
  Map,
  Radio,
  Route,
  ShieldCheck,
  Sparkles,
  Truck,
  User,
  UserCog,
  Users,
} from "lucide-react";
import { Logo } from "./Logo";
import { clearSession, getUser } from "@/lib/auth";

interface NavItem {
  href: string;
  label: string;
  icon: React.ReactNode;
  roles: string[];
}

const NAV: NavItem[] = [
  // ADMIN ROUTES
  {
    href: "/dashboard/admin",
    label: "Tableau de bord",
    icon: <LayoutGrid className="h-5 w-5" />,
    roles: ["ADMIN"],
  },
  {
    href: "/dashboard/admin/users",
    label: "Gestion utilisateurs",
    icon: <Users className="h-5 w-5" />,
    roles: ["ADMIN"],
  },
  {
    href: "/dashboard/admin/requests",
    label: "Demandes de création",
    icon: <FileCheck2 className="h-5 w-5" />,
    roles: ["ADMIN"],
  },
  {
    href: "/dashboard/admin/audit",
    label: "Audit & Sécurité",
    icon: <ShieldCheck className="h-5 w-5" />,
    roles: ["ADMIN"],
  },

  // MANAGER ROUTES
  {
    href: "/dashboard/observatory",
    label: "Observatoire",
    icon: <Activity className="h-5 w-5" />,
    roles: ["MANAGER"],
  },
  {
    href: "/dashboard/overview",
    label: "Tableau de bord",
    icon: <LayoutGrid className="h-5 w-5" />,
    roles: ["MANAGER"],
  },
  {
    href: "/dashboard/map",
    label: "Carte temps réel",
    icon: <Map className="h-5 w-5" />,
    roles: ["MANAGER"],
  },
  {
    href: "/dashboard/corridors",
    label: "Corridors & Zones",
    icon: <Route className="h-5 w-5" />,
    roles: ["MANAGER"],
  },
  {
    href: "/dashboard/drivers",
    label: "Chauffeurs",
    icon: <Truck className="h-5 w-5" />,
    roles: ["MANAGER"],
  },
  {
    href: "/dashboard/ai-decisions",
    label: "Décisions IA",
    icon: <Sparkles className="h-5 w-5 text-amber-400" />,
    roles: ["MANAGER"],
  },
  {
    href: "/dashboard/cargos",
    label: "Cargaisons",
    icon: <Boxes className="h-5 w-5" />,
    roles: ["MANAGER"],
  },
  {
    href: "/dashboard/trackers",
    label: "Trackers",
    icon: <Radio className="h-5 w-5" />,
    roles: ["MANAGER"],
  },
  {
    href: "/dashboard/alerts",
    label: "Alertes",
    icon: <AlertTriangle className="h-5 w-5" />,
    roles: ["MANAGER"],
  },
  {
    href: "/dashboard/managers",
    label: "Managers",
    icon: <UserCog className="h-5 w-5" />,
    roles: ["MANAGER"],
  },

  // DRIVER ROUTES
  {
    href: "/dashboard/driver/overview",
    label: "Mon tableau de bord",
    icon: <LayoutGrid className="h-5 w-5" />,
    roles: ["DRIVER"],
  },
  {
    href: "/dashboard/driver/map",
    label: "Ma carte en direct",
    icon: <Map className="h-5 w-5" />,
    roles: ["DRIVER"],
  },
  {
    href: "/dashboard/deliveries",
    label: "Mes livraisons",
    icon: <Boxes className="h-5 w-5" />,
    roles: ["DRIVER"],
  },
  {
    href: "/dashboard/driver/alerts",
    label: "Alertes & IA",
    icon: <AlertTriangle className="h-5 w-5" />,
    roles: ["DRIVER"],
  },
];

export function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  const router = useRouter();
  const user = getUser();

  const logout = () => {
    clearSession();
    router.push("/login");
  };

  return (
    <aside className="fixed inset-y-0 left-0 z-40 flex w-64 flex-col bg-[#0a101d] text-slate-300 border-r border-slate-800/80">
      <div className="border-b border-slate-800/80 px-5 py-5">
        <Logo dark />
      </div>

      <div className="flex-1 overflow-y-auto px-3 py-4">
        <p className="px-3 pb-2 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
          {user?.role === "MANAGER"
            ? "Pilotage Flotte"
            : user?.role === "DRIVER"
              ? "Espace Chauffeur"
              : "Super Administration"}
        </p>
        <nav className="space-y-1">
          {NAV.filter((n) => n.roles.includes(user?.role || "")).map((item) => {
            const active =
              pathname === item.href ||
              (item.href !== "/dashboard" &&
                pathname.startsWith(item.href + "/"));
            const isObservatory = item.href === "/dashboard/observatory";
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={onNavigate}
                className={[
                  "flex items-center justify-between rounded-xl px-3 py-2.5 text-sm font-medium transition-all duration-150",
                  active
                    ? "bg-blue-600 text-white shadow-lg shadow-blue-600/30 ring-1 ring-blue-400/30 font-semibold"
                    : "text-slate-400 hover:bg-slate-800/60 hover:text-white",
                ].join(" ")}
              >
                <div className="flex items-center gap-3">
                  {item.icon}
                  {item.label}
                </div>
                {isObservatory && (
                  <span className="flex items-center gap-1 rounded-full bg-emerald-500/20 px-2 py-0.5 text-[10px] font-extrabold text-emerald-400 border border-emerald-500/30">
                    <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-ping" />
                    LIVE
                  </span>
                )}
              </Link>
            );
          })}
        </nav>
      </div>

      <div className="border-t border-slate-800/80 p-3">
        <Link
          href="/dashboard/profile"
          onClick={onNavigate}
          title="Voir et modifier mon profil"
          className="mb-2 flex items-center gap-3 rounded-xl px-3 py-2.5 transition hover:bg-slate-800/80 border border-transparent hover:border-slate-700/60 group"
        >
          {user?.avatar_url ? (
            <img
              src={user.avatar_url}
              alt="Photo de profil"
              className="h-10 w-10 rounded-full object-cover ring-2 ring-blue-500/40 shadow"
            />
          ) : (
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-gradient-to-br from-blue-600 to-cyan-500 text-sm font-bold text-white shadow-md shadow-blue-500/20 ring-2 ring-blue-500/30">
              {user?.first_name?.[0] || "R"}
              {user?.last_name?.[0] || ""}
            </div>
          )}
          <div className="min-w-0 flex-1 leading-tight">
            <p className="truncate text-sm font-semibold text-white group-hover:text-blue-400 transition">
              {user?.first_name} {user?.last_name}
            </p>
            <p className="truncate text-xs text-slate-400">
              {user?.role === "ADMIN"
                ? "Administrateur"
                : user?.role === "MANAGER"
                  ? "Manager"
                  : "Chauffeur"}
              {" • "}
              <span className="text-blue-400 group-hover:underline">
                Profil
              </span>
            </p>
          </div>
        </Link>
        <button
          onClick={logout}
          className="flex w-full items-center gap-3 rounded-xl px-3 py-2 text-sm font-medium text-slate-400 transition-colors hover:bg-red-500/10 hover:text-red-400"
        >
          <LogOut className="h-4 w-4" /> Se déconnecter
        </button>
      </div>
    </aside>
  );
}
