"use client";

import { useRef, useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  ArrowRight,
  Building2,
  CloudUpload,
  KeyRound,
  Mail,
  RefreshCw,
  ShieldCheck,
  UserRound,
  CheckCircle2,
  MapPin,
  Globe,
  Phone,
} from "lucide-react";
import AuthShell from "@/components/AuthShell";
import { Button, Input, Select, Textarea } from "@/components/ui";
import { Stepper } from "@/components/Stepper";
import { post, upload } from "@/lib/api";
import { homeRoute, setSession, type User } from "@/lib/auth";
import { MENA_COUNTRIES, getCountryByName, MenaCountry } from "@/lib/menaData";

const steps = [
  { title: "Company", subtitle: "Organization" },
  { title: "Manager", subtitle: "Profile" },
  { title: "Verification", subtitle: "OTP Code" },
  { title: "Security", subtitle: "Password" },
  { title: "Documents", subtitle: "Optional" },
];

interface OrgForm {
  name: string;
  legal_id: string;
  country: string;
  city: string;
  phone: string;
  address: string;
  website: string;
  email: string;
}

interface MgrForm {
  first_name: string;
  last_name: string;
  job_title: string;
  phone: string;
  email: string;
}

export default function RegisterPage() {
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [resending, setResending] = useState(false);
  const [cooldown, setCooldown] = useState(0);
  const [devNotice, setDevNotice] = useState("");

  // Default country: Morocco
  const defaultCountry = MENA_COUNTRIES[0];

  const [selectedCountry, setSelectedCountry] = useState<MenaCountry>(defaultCountry);
  const [availableCities, setAvailableCities] = useState<string[]>(defaultCountry.cities);

  const [org, setOrg] = useState<OrgForm>({
    name: "",
    legal_id: "",
    country: defaultCountry.name,
    city: defaultCountry.cities[0],
    phone: defaultCountry.dialCode + " ",
    address: "",
    website: "",
    email: "",
  });

  const [mgr, setMgr] = useState<MgrForm>({
    first_name: "",
    last_name: "",
    job_title: "",
    phone: defaultCountry.dialCode + " ",
    email: "",
  });

  const [userId, setUserId] = useState("");
  const [orgId, setOrgId] = useState("");
  const [codeInputs, setCodeInputs] = useState<string[]>(Array(6).fill(""));
  const [code, setCode] = useState("");
  const [passwordToken, setPasswordToken] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [certFile, setCertFile] = useState<File | null>(null);
  const [idFile, setIdFile] = useState<File | null>(null);
  const [uploadPct, setUploadPct] = useState(0);
  const refs = useRef<HTMLInputElement[]>([]);

  // When country is changed via dropdown
  const handleCountryChange = (countryName: string) => {
    const country = getCountryByName(countryName) || defaultCountry;
    setSelectedCountry(country);
    setAvailableCities(country.cities);

    // Update phone prefix helper
    const updatePhonePrefix = (currentPhone: string, newPrefix: string) => {
      const match = currentPhone.match(/^\+\d+\s*(.*)$/);
      if (match) {
        return newPrefix + " " + match[1];
      }
      return newPrefix + " " + currentPhone.trim();
    };

    setOrg((prev) => ({
      ...prev,
      country: country.name,
      city: country.cities[0] || "",
      phone: updatePhonePrefix(prev.phone, country.dialCode),
    }));

    setMgr((prev) => ({
      ...prev,
      phone: updatePhonePrefix(prev.phone, country.dialCode),
    }));
  };

  const setOrgField = (k: keyof OrgForm) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
    setOrg((o) => ({ ...o, [k]: e.target.value }));

  const setMgrField = (k: keyof MgrForm) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setMgr((m) => ({ ...m, [k]: e.target.value }));

  const startCooldown = () => {
    setCooldown(30);
    const iv = setInterval(() => {
      setCooldown((c) => {
        if (c <= 1) {
          clearInterval(iv);
          return 0;
        }
        return c - 1;
      });
    }, 1000);
  };

  const submitCompany = async () => {
    setError("");
    setLoading(true);
    try {
      const data = await post<{ user_id: string; organization_id: string; dev_code?: string }>("/auth/register", {
        organization: {
          name: org.name,
          legal_id: org.legal_id,
          country: org.country,
          city: org.city,
          phone: org.phone,
          address: org.address,
          website: org.website || null,
          email: org.email,
        },
        manager: {
          first_name: mgr.first_name,
          last_name: mgr.last_name,
          job_title: mgr.job_title,
          phone: mgr.phone,
          email: mgr.email,
        },
      });
      setUserId(data.user_id);
      setOrgId(data.organization_id);
      if (data.dev_code) {
        setDevNotice(data.dev_code);
      }
      startCooldown();
      setStep(2);
      setTimeout(() => refs.current[0]?.focus(), 100);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create account.");
    } finally {
      setLoading(false);
    }
  };

  const resendCode = async () => {
    setError("");
    setResending(true);
    try {
      const data = await post<{ message: string; dev_code?: string }>("/auth/register/resend", { user_id: userId });
      if (data.dev_code) {
        setDevNotice(data.dev_code);
      }
      startCooldown();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to resend code.");
    } finally {
      setResending(false);
    }
  };

  const verifyCode = async () => {
    setError("");
    setLoading(true);
    try {
      const data = await post<{ password_token: string; user_id: string }>("/auth/register/verify", {
        user_id: userId,
        code,
      });
      setPasswordToken(data.password_token);
      setStep(3);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Invalid code.");
    } finally {
      setLoading(false);
    }
  };

  const complete = async () => {
    setError("");
    setLoading(true);
    try {
      const data = await post<{
        access_token: string;
        user: User;
      }>("/auth/register/complete", {
        password_token: passwordToken,
        password,
        confirm_password: confirm,
      });
      setSession(data.access_token, data.user);
      setStep(4);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to finalize account.");
    } finally {
      setLoading(false);
    }
  };

  const submitDocuments = async (skip = false) => {
    setError("");
    setLoading(true);
    try {
      if (!skip && (certFile || idFile)) {
        const fd = new FormData();
        if (certFile) fd.append("COMPANY_CERTIFICATE", certFile);
        if (idFile) fd.append("RESPONSIBLE_ID", idFile);
        await upload(`/auth/organizations/${orgId}/documents`, fd, setUploadPct);
      }
      router.push(homeRoute("MANAGER"));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to upload documents.");
    } finally {
      setLoading(false);
    }
  };

  const onCodeInput = (i: number, value: string) => {
    const digits = value.replace(/\D/g, "");
    const next = [...codeInputs];
    next[i] = digits.slice(-1);
    setCodeInputs(next);
    const fullCode = next.join("");
    setCode(fullCode);
    if (digits && i < 5) refs.current[i + 1]?.focus();
  };

  const onCodeKeyDown = (i: number, e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Backspace" && !codeInputs[i] && i > 0) {
      refs.current[i - 1]?.focus();
    }
  };

  const onCodePaste = (e: React.ClipboardEvent<HTMLInputElement>) => {
    e.preventDefault();
    const pasted = e.clipboardData.getData("text").replace(/\D/g, "").slice(0, 6);
    if (!pasted) return;
    const next = [...codeInputs];
    for (let i = 0; i < 6; i++) {
      next[i] = pasted[i] || "";
    }
    setCodeInputs(next);
    setCode(next.join(""));
    const nextFocusIdx = Math.min(pasted.length, 5);
    refs.current[nextFocusIdx]?.focus();
  };

  const companyValid =
    org.name.trim().length > 1 &&
    org.legal_id.trim().length > 1 &&
    org.country &&
    org.city &&
    org.phone.trim().length > 4 &&
    org.address.trim().length > 2 &&
    org.email.includes("@");

  const mgrValid =
    mgr.first_name.trim().length > 0 &&
    mgr.last_name.trim().length > 0 &&
    mgr.job_title.trim().length > 0 &&
    mgr.phone.trim().length > 4 &&
    mgr.email.includes("@");

  const downloadLabel = (file: File | null) =>
    file ? file.name : "No file chosen";

  return (
    <AuthShell maxWidth="max-w-3xl">
      <Link
        href="/login"
        className="mb-5 inline-flex items-center gap-1.5 text-xs font-medium text-slate-400 hover:text-blue-400 transition"
      >
        <ArrowLeft className="h-3.5 w-3.5" /> Back to login
      </Link>

      <div className="mb-6">
        <h2 className="text-2xl font-bold tracking-tight text-white">
          Create Company Account
        </h2>
        <p className="mt-1 text-xs text-slate-400">
          Resilience & logistics management platform for MENA corridors
        </p>
      </div>

      <div className="mb-6">
        <Stepper steps={steps} current={step} />
      </div>

      {/* STEP 0: COMPANY */}
      {step === 0 && (
        <div className="space-y-4">
          <div className="flex items-center gap-2 border-b border-slate-800 pb-2 text-sm font-semibold text-blue-400">
            <Building2 className="h-4 w-4" /> 1. Company Information
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Input
              label="Company Name"
              value={org.name}
              onChange={setOrgField("name")}
              placeholder="e.g. LogiTrans MENA"
              required
            />
            <Input
              label="Commercial Register / Tax ID"
              value={org.legal_id}
              onChange={setOrgField("legal_id")}
              placeholder="e.g. 002145896000034"
              required
            />
          </div>

          {/* MENA Country and City Selects */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label className="mb-1.5 flex items-center gap-1 text-xs font-semibold uppercase tracking-wider text-slate-300">
                <Globe className="h-3 w-3 text-blue-400" /> Country (MENA Region)
              </label>
              <select
                value={org.country}
                onChange={(e) => handleCountryChange(e.target.value)}
                className="w-full rounded-xl border border-slate-700/80 bg-[#0a101d] px-3.5 py-2.5 text-sm text-slate-100 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
              >
                {MENA_COUNTRIES.map((c) => (
                  <option key={c.code} value={c.name} className="bg-[#0f172a] text-white">
                    {c.flag} {c.name} ({c.name_ar}) {c.dialCode}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="mb-1.5 flex items-center gap-1 text-xs font-semibold uppercase tracking-wider text-slate-300">
                <MapPin className="h-3 w-3 text-blue-400" /> City
              </label>
              <select
                value={org.city}
                onChange={setOrgField("city")}
                className="w-full rounded-xl border border-slate-700/80 bg-[#0a101d] px-3.5 py-2.5 text-sm text-slate-100 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
              >
                {availableCities.map((cityName) => (
                  <option key={cityName} value={cityName} className="bg-[#0f172a] text-white">
                    {cityName}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label className="mb-1.5 flex items-center gap-1 text-xs font-semibold uppercase tracking-wider text-slate-300">
                <Phone className="h-3 w-3 text-blue-400" /> Company Phone
              </label>
              <input
                type="text"
                value={org.phone}
                onChange={setOrgField("phone")}
                placeholder={selectedCountry.dialCode + " 5 22 ..."}
                required
                className="w-full rounded-xl border border-slate-700/80 bg-[#0a101d] px-3.5 py-2.5 text-sm font-mono text-slate-100 placeholder:text-slate-500 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
              />
            </div>

            <div>
              <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-slate-300">
                Company Contact Email
              </label>
              <input
                type="email"
                value={org.email}
                onChange={setOrgField("email")}
                placeholder="contact@company.com"
                required
                className="w-full rounded-xl border border-slate-700/80 bg-[#0a101d] px-3.5 py-2.5 text-sm text-slate-100 placeholder:text-slate-500 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
              />
            </div>
          </div>

          <Input
            label="Website (optional)"
            value={org.website}
            onChange={setOrgField("website")}
            placeholder="https://..."
          />

          <Textarea
            label="Headquarters Address"
            value={org.address}
            onChange={setOrgField("address")}
            placeholder="Full headquarters or logistics center address"
            required
          />

          {error && (
            <div className="rounded-xl border border-red-500/30 bg-red-950/40 px-4 py-3 text-sm font-medium text-red-300">
              {error}
            </div>
          )}

          <Button
            type="button"
            variant="figma"
            onClick={() => setStep(1)}
            disabled={!companyValid}
            className="w-full py-3"
          >
            Next Step (Manager) <ArrowRight className="h-4 w-4 ml-1" />
          </Button>
        </div>
      )}

      {/* STEP 1: MANAGER */}
      {step === 1 && (
        <div className="space-y-4">
          <div className="flex items-center gap-2 border-b border-slate-800 pb-2 text-sm font-semibold text-blue-400">
            <UserRound className="h-4 w-4" /> 2. Account Manager (Primary Manager)
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Input
              label="First Name"
              value={mgr.first_name}
              onChange={setMgrField("first_name")}
              placeholder="Karim"
              required
            />
            <Input
              label="Last Name"
              value={mgr.last_name}
              onChange={setMgrField("last_name")}
              placeholder="El Amrani"
              required
            />
          </div>

          <Input
            label="Job Title / Role"
            value={mgr.job_title}
            onChange={setMgrField("job_title")}
            placeholder="Operations / Fleet Director"
            required
          />

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label className="mb-1.5 flex items-center gap-1 text-xs font-semibold uppercase tracking-wider text-slate-300">
                <Phone className="h-3 w-3 text-blue-400" /> Mobile Phone
              </label>
              <input
                type="text"
                value={mgr.phone}
                onChange={setMgrField("phone")}
                placeholder={selectedCountry.dialCode + " 6 61 ..."}
                required
                className="w-full rounded-xl border border-slate-700/80 bg-[#0a101d] px-3.5 py-2.5 text-sm font-mono text-slate-100 placeholder:text-slate-500 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
              />
            </div>

            <div>
              <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-slate-300">
                Personal Professional Email
              </label>
              <input
                type="email"
                value={mgr.email}
                onChange={setMgrField("email")}
                placeholder="manager@company.com"
                required
                className="w-full rounded-xl border border-slate-700/80 bg-[#0a101d] px-3.5 py-2.5 text-sm text-slate-100 placeholder:text-slate-500 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
              />
            </div>
          </div>

          <div className="rounded-xl border border-blue-500/20 bg-blue-950/20 p-3 text-xs text-blue-300">
            <span className="font-semibold">Important note:</span> The 6-digit verification code will be sent directly to this email.
          </div>

          {error && (
            <div className="rounded-xl border border-red-500/30 bg-red-950/40 px-4 py-3 text-sm font-medium text-red-300">
              {error}
            </div>
          )}

          <div className="flex gap-3 pt-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => setStep(0)}
              className="flex-1 py-3"
            >
              <ArrowLeft className="h-4 w-4 mr-1" /> Previous
            </Button>
            <Button
              type="button"
              variant="figma"
              onClick={submitCompany}
              loading={loading}
              disabled={!mgrValid}
              className="flex-1 py-3"
            >
              Create Account & Send Code <ArrowRight className="h-4 w-4 ml-1" />
            </Button>
          </div>
        </div>
      )}

      {/* STEP 2: VERIFICATION OTP */}
      {step === 2 && (
        <div className="space-y-5 text-center">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-blue-600/20 text-blue-400 ring-1 ring-blue-500/30">
            <Mail className="h-6 w-6" />
          </div>

          <div>
            <h3 className="text-lg font-bold text-white">Email Verification</h3>
            <p className="mt-1 text-xs text-slate-400">
              We sent a 6-digit code to <span className="font-semibold text-slate-200">{mgr.email}</span>
            </p>
          </div>

          {/* 6-digit OTP code inputs */}
          <div className="flex justify-center gap-2 sm:gap-3 py-2">
            {codeInputs.map((val, idx) => (
              <input
                key={idx}
                ref={(el) => {
                  if (el) refs.current[idx] = el;
                }}
                type="text"
                inputMode="numeric"
                maxLength={1}
                value={val}
                onChange={(e) => onCodeInput(idx, e.target.value)}
                onKeyDown={(e) => onCodeKeyDown(idx, e)}
                onPaste={idx === 0 ? onCodePaste : undefined}
                className="h-12 w-11 sm:h-14 sm:w-12 rounded-xl border border-slate-700 bg-[#0a101d] text-center text-xl font-mono font-bold text-white outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/30"
              />
            ))}
          </div>

          {devNotice && (
            <div className="rounded-xl border border-emerald-500/30 bg-emerald-950/30 p-3.5 text-left text-xs text-emerald-300 flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-lg">
              <div>
                <p className="font-semibold text-emerald-200">Verification code (Simulation / Local):</p>
                <p className="font-mono text-base font-bold text-white tracking-widest mt-0.5">{devNotice}</p>
              </div>
              <button
                type="button"
                onClick={() => {
                  const digits = devNotice.slice(0, 6).split("");
                  setCodeInputs(digits);
                  setCode(devNotice);
                }}
                className="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold shadow transition whitespace-nowrap self-start sm:self-auto"
              >
                Auto-fill
              </button>
            </div>
          )}

          {error && (
            <div className="rounded-xl border border-red-500/30 bg-red-950/40 px-4 py-3 text-xs font-medium text-red-300">
              {error}
            </div>
          )}

          <div className="space-y-3 pt-2">
            <Button
              type="button"
              variant="figma"
              onClick={verifyCode}
              loading={loading}
              disabled={code.length !== 6}
              className="w-full py-3"
            >
              Verify Code <ArrowRight className="h-4 w-4 ml-1" />
            </Button>

            <button
              type="button"
              onClick={resendCode}
              disabled={resending || cooldown > 0}
              className="text-xs font-medium text-slate-400 hover:text-blue-400 disabled:opacity-50 transition"
            >
              {cooldown > 0 ? `Resend code in ${cooldown}s` : "Didn't receive code? Resend"}
            </button>
          </div>
        </div>
      )}

      {/* STEP 3: PASSWORD */}
      {step === 3 && (
        <div className="space-y-4">
          <div className="flex items-center gap-2 border-b border-slate-800 pb-2 text-sm font-semibold text-blue-400">
            <KeyRound className="h-4 w-4" /> 4. Account Security
          </div>

          <Input
            label="Set Password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="8 characters minimum"
            required
          />

          <Input
            label="Confirm Password"
            type="password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            placeholder="Repeat your password"
            required
          />

          {error && (
            <div className="rounded-xl border border-red-500/30 bg-red-950/40 px-4 py-3 text-sm font-medium text-red-300">
              {error}
            </div>
          )}

          <Button
            type="button"
            variant="figma"
            onClick={complete}
            loading={loading}
            disabled={password.length < 8 || password !== confirm}
            className="w-full py-3"
          >
            Confirm Password <ArrowRight className="h-4 w-4 ml-1" />
          </Button>
        </div>
      )}

      {/* STEP 4: DOCUMENTS & FINALIZATION */}
      {step === 4 && (
        <div className="space-y-5 text-center">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-emerald-500/20 text-emerald-400 ring-1 ring-emerald-500/30">
            <CheckCircle2 className="h-6 w-6" />
          </div>

          <div>
            <h3 className="text-lg font-bold text-white">Account configured successfully!</h3>
            <p className="mt-1 text-xs text-slate-400">
              You can now upload verification documents for administrator review, or skip this step.
            </p>
          </div>

          <div className="space-y-3 text-left">
            <div className="rounded-xl border border-slate-800 bg-[#0a101d] p-3.5">
              <label className="mb-1 block text-xs font-semibold text-slate-300">
                Company Registration Certificate (PDF, JPG)
              </label>
              <input
                type="file"
                accept=".pdf,.jpg,.jpeg,.png"
                onChange={(e) => setCertFile(e.target.files?.[0] || null)}
                className="text-xs text-slate-400 file:mr-3 file:rounded-lg file:border-0 file:bg-slate-800 file:px-3 file:py-1.5 file:text-xs file:font-semibold file:text-slate-200 hover:file:bg-slate-700"
              />
            </div>

            <div className="rounded-xl border border-slate-800 bg-[#0a101d] p-3.5">
              <label className="mb-1 block text-xs font-semibold text-slate-300">
                Manager ID Document (Passport / National ID)
              </label>
              <input
                type="file"
                accept=".pdf,.jpg,.jpeg,.png"
                onChange={(e) => setIdFile(e.target.files?.[0] || null)}
                className="text-xs text-slate-400 file:mr-3 file:rounded-lg file:border-0 file:bg-slate-800 file:px-3 file:py-1.5 file:text-xs file:font-semibold file:text-slate-200 hover:file:bg-slate-700"
              />
            </div>
          </div>

          {error && (
            <div className="rounded-xl border border-red-500/30 bg-red-950/40 px-4 py-3 text-xs font-medium text-red-300">
              {error}
            </div>
          )}

          <div className="flex gap-3 pt-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => submitDocuments(true)}
              disabled={loading}
              className="flex-1 py-3"
            >
              Skip this step
            </Button>
            <Button
              type="button"
              variant="figma"
              onClick={() => submitDocuments(false)}
              loading={loading}
              className="flex-1 py-3"
            >
              Finish & Continue <ArrowRight className="h-4 w-4 ml-1" />
            </Button>
          </div>
        </div>
      )}
    </AuthShell>
  );
}
