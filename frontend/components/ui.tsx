"use client";

import React, { useEffect } from "react";
import { Loader2, X } from "lucide-react";

export function Spinner({ className = "" }: { className?: string }) {
  return <Loader2 className={`h-5 w-5 animate-spin ${className}`} />;
}

type ButtonVariant = "primary" | "figma" | "outline" | "ghost" | "danger";

export function Button({
  children,
  variant = "figma",
  size = "md",
  loading,
  className = "",
  disabled,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  size?: "sm" | "md" | "lg";
  loading?: boolean;
}) {
  const sizeClass =
    size === "sm" ? "px-3 py-1.5 text-xs" : size === "lg" ? "px-5 py-3 text-base" : "px-4 py-2.5 text-sm";
  const variantClass =
    variant === "figma"
      ? "bg-blue-600 hover:bg-blue-500 text-white shadow-lg shadow-blue-600/30 ring-1 ring-blue-400/30 active:scale-[0.99] font-medium"
      : variant === "primary"
      ? "btn-primary"
      : variant === "outline"
      ? "border border-slate-700 bg-slate-800/80 text-slate-200 hover:bg-slate-700/80"
      : variant === "danger"
      ? "btn-danger"
      : "text-slate-300 hover:bg-slate-800/60";
  return (
    <button
      className={`inline-flex items-center justify-center gap-2 rounded-xl font-semibold transition-all duration-200 disabled:cursor-not-allowed disabled:opacity-50 ${sizeClass} ${variantClass} ${className}`}
      disabled={disabled || loading}
      {...props}
    >
      {loading && <Spinner className="h-4 w-4" />}
      {children}
    </button>
  );
}

export function Input({
  label,
  error,
  className = "",
  dark = true,
  ...props
}: React.InputHTMLAttributes<HTMLInputElement> & {
  label?: string;
  error?: string;
  dark?: boolean;
}) {
  return (
    <div className="w-full">
      {label && (
        <label className={`mb-1.5 block text-xs font-semibold uppercase tracking-wider ${dark ? "text-slate-300" : "text-slate-600"}`}>
          {label}
        </label>
      )}
      <input
        className={`w-full rounded-xl px-3.5 py-2.5 text-sm outline-none transition-all duration-150 ${
          dark
            ? "border border-slate-700/80 bg-[#0a101d] text-slate-100 placeholder:text-slate-500 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
            : "border border-slate-300 bg-white text-slate-800 placeholder:text-slate-400 focus:border-blue-600 focus:ring-2 focus:ring-blue-500/20"
        } ${className}`}
        {...props}
      />
      {error && <p className="mt-1 text-xs font-medium text-red-400">{error}</p>}
    </div>
  );
}

export function Textarea({
  label,
  error,
  className = "",
  dark = true,
  ...props
}: React.TextareaHTMLAttributes<HTMLTextAreaElement> & {
  label?: string;
  error?: string;
  dark?: boolean;
}) {
  return (
    <div className="w-full">
      {label && (
        <label className={`mb-1.5 block text-xs font-semibold uppercase tracking-wider ${dark ? "text-slate-300" : "text-slate-600"}`}>
          {label}
        </label>
      )}
      <textarea
        className={`min-h-[100px] w-full rounded-xl px-3.5 py-2.5 text-sm outline-none transition-all duration-150 ${
          dark
            ? "border border-slate-700/80 bg-[#0a101d] text-slate-100 placeholder:text-slate-500 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
            : "border border-slate-300 bg-white text-slate-800 placeholder:text-slate-400 focus:border-blue-600 focus:ring-2 focus:ring-blue-500/20"
        } ${className}`}
        {...props}
      />
      {error && <p className="mt-1 text-xs font-medium text-red-400">{error}</p>}
    </div>
  );
}

export function Select({
  label,
  error,
  className = "",
  dark = true,
  children,
  ...props
}: React.SelectHTMLAttributes<HTMLSelectElement> & {
  label?: string;
  error?: string;
  dark?: boolean;
}) {
  return (
    <div className="w-full">
      {label && (
        <label className={`mb-1.5 block text-xs font-semibold uppercase tracking-wider ${dark ? "text-slate-300" : "text-slate-600"}`}>
          {label}
        </label>
      )}
      <select
        className={`w-full rounded-xl px-3.5 py-2.5 text-sm outline-none transition-all duration-150 ${
          dark
            ? "border border-slate-700/80 bg-[#0a101d] text-slate-100 placeholder:text-slate-500 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
            : "border border-slate-300 bg-white text-slate-800 placeholder:text-slate-400 focus:border-blue-600 focus:ring-2 focus:ring-blue-500/20"
        } ${className}`}
        {...props}
      >
        {children}
      </select>
      {error && <p className="mt-1 text-xs font-medium text-red-400">{error}</p>}
    </div>
  );
}

export function Card({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return <div className={`card ${className}`}>{children}</div>;
}

const severityStyles: Record<string, string> = {
  LOW: "bg-slate-100 text-slate-600",
  MEDIUM: "bg-amber-100 text-amber-700",
  HIGH: "bg-orange-100 text-orange-700",
  CRITICAL: "bg-red-100 text-red-700",
  NORMAL: "bg-emerald-100 text-emerald-700",
  EVENT: "bg-amber-100 text-amber-700",
  INCIDENT: "bg-orange-100 text-orange-700",
  CRISIS: "bg-red-100 text-red-700",
  OPEN: "bg-red-100 text-red-700",
  ACKNOWLEDGED: "bg-amber-100 text-amber-700",
  CLOSED: "bg-slate-100 text-slate-600",
  PENDING: "bg-slate-100 text-slate-600",
  APPROVED: "bg-emerald-100 text-emerald-700",
  REJECTED: "bg-red-100 text-red-700",
  ACTIVE: "bg-emerald-100 text-emerald-700",
  IN_TRANSIT: "bg-teal-100 text-teal-700",
  DELIVERED: "bg-emerald-100 text-emerald-700",
  INVITED: "bg-blue-100 text-blue-700",
  DISABLED: "bg-slate-200 text-slate-500",
};

const labelMap: Record<string, string> = {
  LOW: "Low",
  MEDIUM: "Medium",
  HIGH: "High",
  CRITICAL: "Critical",
  NORMAL: "Normal",
  EVENT: "Event",
  INCIDENT: "Incident",
  CRISIS: "Crisis",
  OPEN: "Open",
  ACKNOWLEDGED: "Acknowledged",
  CLOSED: "Closed",
  PENDING: "Pending",
  APPROVED: "Approved",
  REJECTED: "Rejected",
  ACTIVE: "Active",
  IN_TRANSIT: "In Transit",
  DELIVERED: "Delivered",
  INVITED: "Invited",
  DISABLED: "Disabled",
  SUCCESS: "Success",
  WARNING: "Warning",
  DANGER: "Danger",
};

export function Badge({
  value,
  children,
  variant,
  className = "",
}: {
  value?: string;
  children?: React.ReactNode;
  variant?: string;
  className?: string;
}) {
  const key = (variant || value || "").toUpperCase();
  const text = children || labelMap[key] || value?.replace(/_/g, " ") || "";
  const style =
    key === "SUCCESS" || key === "APPROVED" || key === "ACTIVE" || key === "DELIVERED"
      ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
      : key === "WARNING" || key === "PENDING" || key === "MEDIUM" || key === "INVITED"
      ? "bg-amber-500/20 text-amber-300 border border-amber-500/30"
      : key === "DANGER" || key === "CRITICAL" || key === "REJECTED" || key === "HIGH"
      ? "bg-red-500/20 text-red-300 border border-red-500/30"
      : severityStyles[key] || "bg-slate-800 text-slate-300 border border-slate-700";

  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${style} ${className}`}>
      {text}
    </span>
  );
}

export function Modal({
  open = true,
  onClose,
  title,
  description,
  children,
  wide,
}: {
  open?: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children: React.ReactNode;
  wide?: boolean;
}) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={onClose} />
      <div
        className={`relative w-full ${wide ? "max-w-3xl" : "max-w-lg"} max-h-[90vh] overflow-y-auto rounded-2xl bg-[#0f172a] border border-slate-800 p-6 shadow-2xl text-slate-100`}
      >
        <div className="mb-4 flex items-start justify-between gap-3">
          <div>
            <h3 className="text-lg font-bold text-white tracking-tight">{title}</h3>
            {description && <p className="text-xs text-slate-400 mt-1">{description}</p>}
          </div>
          <button onClick={onClose} className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-800 hover:text-white transition">
            <X className="h-5 w-5" />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

export function EmptyState({
  title,
  description,
  icon,
  action,
  children,
}: {
  title: string;
  description?: string;
  icon?: React.ReactNode;
  action?: React.ReactNode;
  children?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-slate-800 bg-[#0a101d]/50 px-6 py-14 text-center">
      {icon && <div className="mb-3 text-slate-500">{icon}</div>}
      <p className="text-sm font-semibold text-slate-200">{title}</p>
      {description && <p className="mt-1 max-w-sm text-xs text-slate-400">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
      {children && <div className="mt-4">{children}</div>}
    </div>
  );
}