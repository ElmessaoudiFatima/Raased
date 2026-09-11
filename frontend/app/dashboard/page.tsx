"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { getUser, isAuthenticated } from "@/lib/auth";

export default function DashboardIndex() {
  const router = useRouter();

  useEffect(() => {
    if (!isAuthenticated()) {
      router.replace("/login");
      return;
    }
    const user = getUser();
    if (user?.role === "ADMIN") router.replace("/dashboard/admin/organizations");
    else if (user?.role === "DRIVER") router.replace("/dashboard/map");
    else router.replace("/dashboard/overview");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return null;
}