"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { Sidebar } from "@/components/Sidebar";
import { ShellContext } from "@/components/ShellContext";
import { ToastProvider } from "@/components/Toasts";
import { isAuthenticated } from "@/lib/auth";
import { Loader2 } from "lucide-react";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [ready, setReady] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [shellValue, setShellValue] = useState({ openMobileMenu: () => setMobileOpen(true) });

  useEffect(() => {
    setShellValue({ openMobileMenu: () => setMobileOpen(true) });
  }, []);

  useEffect(() => {
    if (!isAuthenticated()) {
      router.replace("/login");
    } else {
      setReady(true);
    }
  }, [router, pathname]);

  if (!ready) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-raased-navy">
        <Loader2 className="h-8 w-8 animate-spin text-raased-teal-light" />
      </div>
    );
  }

  return (
    <ToastProvider>
      <ShellContext.Provider value={shellValue}>
        <div className="min-h-screen bg-[#080d1a] text-slate-100">
          <div className="hidden lg:block">
            <Sidebar />
          </div>
          {mobileOpen && (
            <div className="fixed inset-0 z-40 lg:hidden">
              <div className="absolute inset-0 bg-black/50" onClick={() => setMobileOpen(false)} />
              <Sidebar onNavigate={() => setMobileOpen(false)} />
            </div>
          )}
          <main className="lg:pl-64">{children}</main>
        </div>
      </ShellContext.Provider>
    </ToastProvider>
  );
}