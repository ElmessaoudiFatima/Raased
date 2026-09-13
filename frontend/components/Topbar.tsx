"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Bell, LogOut, Menu } from "lucide-react";
import { get } from "@/lib/api";
import { clearSession, getUser } from "@/lib/auth";

export function Topbar({
  title,
  subtitle,
  onMenu,
}: {
  title: string;
  subtitle?: string;
  onMenu?: () => void;
}) {
  const router = useRouter();
  const user = getUser();
  const [alerts, setAlerts] = useState(0);

  useEffect(() => {
    if (!user) return;
    const role = user.role;
    const url = role === "DRIVER" ? "/drivers/alerts" : "/managers/alerts";
    get<{ alerts: unknown[] }>(url)
      .then((d) => {
        setAlerts(Array.isArray(d.alerts) ? d.alerts.length : 0);
      })
      .catch(() => {});
  }, [user]);

  const logout = () => {
    clearSession();
    router.push("/login");
  };

  const orgPending = user?.role === "MANAGER" && user.organization?.status === "PENDING";

  return (
    <header className="sticky top-0 z-30 border-b border-slate-800/80 bg-[#0a101d]/90 backdrop-blur">
      <div className="flex items-center justify-between gap-4 px-6 py-4">
        <div className="flex items-center gap-3">
          <button
            onClick={onMenu}
            className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-800 lg:hidden"
          >
            <Menu className="h-5 w-5" />
          </button>
          <div>
            <h1 className="text-lg font-bold text-white tracking-tight">{title}</h1>
            {subtitle && <p className="text-xs text-slate-400">{subtitle}</p>}
          </div>
          {orgPending && (
            <span className="badge ml-2 bg-amber-500/20 text-amber-300 border border-amber-500/30">
              Company pending approval
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => router.push("/dashboard/alerts")}
            className="relative rounded-xl border border-slate-800 bg-[#0f172a] p-2.5 text-slate-300 transition hover:bg-slate-800 hover:text-white"
            title="Alerts"
          >
            <Bell className="h-4 w-4" />
            {alerts > 0 && (
              <span className="absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-bold text-white">
                {alerts > 9 ? "9+" : alerts}
              </span>
            )}
          </button>

          {/* Profile button */}
          <button
            onClick={() => router.push("/dashboard/profile")}
            title="My Profile & Photo"
            className="flex items-center gap-2 rounded-xl border border-slate-800 bg-[#0f172a] px-2.5 py-1.5 text-xs font-semibold text-slate-200 transition hover:border-blue-500/50 hover:bg-slate-800/80"
          >
            {user?.avatar_url ? (
              <img
                src={user.avatar_url}
                alt="Avatar"
                className="h-6 w-6 rounded-full object-cover ring-1 ring-blue-500"
              />
            ) : (
              <div className="flex h-6 w-6 items-center justify-center rounded-full bg-gradient-to-br from-blue-600 to-cyan-500 text-[10px] font-bold text-white">
                {user?.first_name?.[0] || "U"}
              </div>
            )}
            <span className="hidden md:inline">{user?.first_name}</span>
          </button>

          <button
            onClick={logout}
            className="hidden items-center gap-1.5 rounded-xl border border-slate-800 bg-[#0f172a] px-3 py-2 text-xs font-semibold text-slate-300 transition hover:bg-red-500/10 hover:text-red-400 hover:border-red-500/30 sm:flex"
          >
            <LogOut className="h-3.5 w-3.5" /> Sign Out
          </button>
        </div>
      </div>
    </header>
  );
}