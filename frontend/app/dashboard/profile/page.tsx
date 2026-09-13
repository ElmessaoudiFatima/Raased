"use client";

import { useEffect, useRef, useState } from "react";
import {
  Building2,
  Camera,
  CheckCircle2,
  Mail,
  Phone,
  Save,
  ShieldCheck,
  Upload,
  User as UserIcon,
} from "lucide-react";
import { get, patch } from "@/lib/api";
import { getToken, getUser, setSession, User } from "@/lib/auth";
import { Button, Input } from "@/components/ui";

export default function ProfilePage() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [success, setSuccess] = useState("");
  const [error, setError] = useState("");

  const [form, setForm] = useState({
    first_name: "",
    last_name: "",
    phone: "",
    job_title: "",
    avatar_url: "",
  });

  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const local = getUser();
    if (local) {
      setUser(local);
      setForm({
        first_name: local.first_name || "",
        last_name: local.last_name || "",
        phone: local.phone || "",
        job_title: local.job_title || "",
        avatar_url: local.avatar_url || "",
      });
    }

    get<{ user: User }>("/auth/me")
      .then((d) => {
        setUser(d.user);
        const token = getToken() || "";
        setSession(token, d.user);
        setForm({
          first_name: d.user.first_name || "",
          last_name: d.user.last_name || "",
          phone: d.user.phone || "",
          job_title: d.user.job_title || "",
          avatar_url: d.user.avatar_url || "",
        });
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const handleImageUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!file.type.startsWith("image/")) {
      setError("Please select a valid image file (JPG, PNG, WebP).");
      return;
    }

    if (file.size > 5 * 1024 * 1024) {
      setError("Image must not exceed 5 MB.");
      return;
    }

    const reader = new FileReader();
    reader.onload = () => {
      const base64 = reader.result as string;
      setForm((f) => ({ ...f, avatar_url: base64 }));
      setSuccess("Photo selected! Don't forget to save.");
    };
    reader.readAsDataURL(file);
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSuccess("");
    setSaving(true);

    try {
      const data = await patch<{ user: User; message: string }>("/auth/profile", form);
      setUser(data.user);
      const token = getToken() || "";
      setSession(token, data.user);
      setSuccess("Profile and photo updated successfully!");
      setTimeout(() => setSuccess(""), 4000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error during update.");
    } finally {
      setSaving(false);
    }
  };

  if (loading && !user) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-blue-500 border-t-transparent" />
      </div>
    );
  }

  const roleLabel =
    user?.role === "ADMIN"
      ? "Super Administrator"
      : user?.role === "MANAGER"
      ? "Fleet & Operations Manager"
      : "Truck Driver";

  const roleBadgeColor =
    user?.role === "ADMIN"
      ? "bg-purple-500/20 text-purple-300 border-purple-500/30"
      : user?.role === "MANAGER"
      ? "bg-blue-500/20 text-blue-300 border-blue-500/30"
      : "bg-emerald-500/20 text-emerald-300 border-emerald-500/30";

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Header Banner */}
      <div className="relative overflow-hidden rounded-2xl border border-slate-800 bg-gradient-to-r from-[#0f172a] via-[#131d33] to-[#0a101d] p-6 sm:p-8 shadow-xl">
        <div className="absolute right-0 top-0 h-full w-1/3 bg-radial from-blue-600/10 via-transparent to-transparent pointer-events-none" />
        
        <div className="relative flex flex-col sm:flex-row items-center sm:items-start gap-6">
          {/* Avatar with upload trigger */}
          <div className="relative group">
            {form.avatar_url ? (
              <img
                src={form.avatar_url}
                alt="Profile picture"
                className="h-24 w-24 sm:h-28 sm:w-28 rounded-2xl object-cover ring-4 ring-blue-500/30 shadow-2xl transition duration-200 group-hover:brightness-75"
              />
            ) : (
              <div className="flex h-24 w-24 sm:h-28 sm:w-28 items-center justify-center rounded-2xl bg-gradient-to-br from-blue-600 to-cyan-500 text-3xl font-extrabold text-white shadow-2xl ring-4 ring-blue-500/30">
                {user?.first_name?.[0] || "R"}
                {user?.last_name?.[0] || ""}
              </div>
            )}
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="absolute inset-0 flex flex-col items-center justify-center gap-1 rounded-2xl bg-black/60 text-white opacity-0 transition duration-200 group-hover:opacity-100"
              title="Change photo"
            >
              <Camera className="h-6 w-6 text-blue-400" />
              <span className="text-[11px] font-semibold">Edit</span>
            </button>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              className="hidden"
              onChange={handleImageUpload}
            />
          </div>

          {/* User Info Quick summary */}
          <div className="text-center sm:text-left flex-1 space-y-2">
            <div className="flex flex-wrap items-center justify-center sm:justify-start gap-2.5">
              <h2 className="text-2xl font-bold text-white tracking-tight">
                {user?.first_name} {user?.last_name}
              </h2>
              <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold border ${roleBadgeColor}`}>
                <ShieldCheck className="h-3.5 w-3.5" /> {roleLabel}
              </span>
            </div>

            <p className="text-sm text-slate-400 flex items-center justify-center sm:justify-start gap-2">
              <Mail className="h-3.5 w-3.5 text-slate-500" /> {user?.email}
              {user?.phone && (
                <>
                  <span className="text-slate-600">•</span>
                  <Phone className="h-3.5 w-3.5 text-slate-500" /> {user.phone}
                </>
              )}
            </p>

            {user?.organization && (
              <div className="inline-flex items-center gap-2 rounded-xl bg-slate-800/60 px-3 py-1.5 text-xs text-slate-300 border border-slate-700/50">
                <Building2 className="h-3.5 w-3.5 text-blue-400" />
                <span>
                  <strong className="text-white">{user.organization.name}</strong> ({user.organization.city}, {user.organization.country})
                </span>
              </div>
            )}
          </div>

          <Button
            type="button"
            variant="outline"
            onClick={() => fileInputRef.current?.click()}
            className="text-xs shrink-0 flex items-center gap-1.5"
          >
            <Upload className="h-3.5 w-3.5" /> Change photo
          </Button>
        </div>
      </div>

      {/* Notifications */}
      {success && (
        <div className="rounded-xl border border-emerald-500/30 bg-emerald-950/40 p-4 text-sm text-emerald-300 flex items-center gap-2">
          <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-400" />
          {success}
        </div>
      )}

      {error && (
        <div className="rounded-xl border border-red-500/30 bg-red-950/40 p-4 text-sm text-red-300">
          {error}
        </div>
      )}

      {/* Profile Form */}
      <form onSubmit={handleSave} className="rounded-2xl border border-slate-800 bg-[#0f172a] p-6 sm:p-8 space-y-6 shadow-lg">
        <div>
          <h3 className="text-lg font-bold text-white flex items-center gap-2">
            <UserIcon className="h-5 w-5 text-blue-400" /> Personal Information
          </h3>
          <p className="text-xs text-slate-400 mt-0.5">
            Manage your name, phone number and your role within the organization.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Input
            label="First Name"
            value={form.first_name}
            onChange={(e) => setForm({ ...form, first_name: e.target.value })}
            required
          />
          <Input
            label="Last Name"
            value={form.last_name}
            onChange={(e) => setForm({ ...form, last_name: e.target.value })}
            required
          />
          <Input
            label="Phone Number"
            value={form.phone}
            placeholder="+212 600 00 00 00"
            onChange={(e) => setForm({ ...form, phone: e.target.value })}
          />
          <Input
            label="Role / Title"
            value={form.job_title}
            placeholder="Logistics Director, Driver..."
            onChange={(e) => setForm({ ...form, job_title: e.target.value })}
          />
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2 border-t border-slate-800/80">
          <div>
            <label className="block text-xs font-semibold text-slate-400 mb-1">
              Email Address (Login Identifier)
            </label>
            <input
              disabled
              value={user?.email || ""}
              className="w-full rounded-xl border border-slate-800 bg-slate-900/60 px-3.5 py-2.5 text-sm text-slate-400 cursor-not-allowed"
            />
            <p className="text-[11px] text-slate-500 mt-1">Email address is linked to authentication and cannot be changed.</p>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-400 mb-1">
              Platform Role
            </label>
            <input
              disabled
              value={roleLabel}
              className="w-full rounded-xl border border-slate-800 bg-slate-900/60 px-3.5 py-2.5 text-sm text-slate-400 cursor-not-allowed"
            />
            <p className="text-[11px] text-slate-500 mt-1">Assigned by the Raased administrator.</p>
          </div>
        </div>

        <div className="flex justify-end pt-4">
          <Button
            type="submit"
            variant="figma"
            loading={saving}
            className="px-6 py-2.5 flex items-center gap-2"
          >
            <Save className="h-4 w-4" /> Save changes
          </Button>
        </div>
      </form>
    </div>
  );
}
