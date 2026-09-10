"use client";

import { useState } from "react";
import { Topbar } from "@/components/Topbar";
import { useShell } from "@/components/ShellContext";
import { DynamicCorridorCenter } from "@/components/DynamicCorridorCenter";
import { Activity, ShieldCheck } from "lucide-react";

export default function ObservatoryPage() {
  const { openMobileMenu } = useShell();

  return (
    <div className="min-h-screen bg-[#0a101d] text-slate-100">
      <Topbar
        title="Observatoire Dynamique"
        subtitle="Supervision en temps réel des corridors logistiques et des signaux CAMARA"
        onMenu={openMobileMenu}
      />

      <div className="p-4 sm:p-6 lg:p-8">
        <DynamicCorridorCenter />
      </div>
    </div>
  );
}
