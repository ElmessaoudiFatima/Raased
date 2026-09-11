import { get } from "./api";

export interface User {
  id: string;
  first_name: string;
  last_name: string;
  email: string;
  role: "ADMIN" | "MANAGER" | "DRIVER";
  job_title?: string | null;
  phone?: string | null;
  avatar_url?: string | null;
  email_verified: boolean;
  account_status: string;
  is_active: boolean;
  organization_id?: string | null;
  organization?: {
    id: string;
    name: string;
    city: string;
    country: string;
    status: string;
  } | null;
}

const TOKEN_KEY = "raased_token";
const USER_KEY = "raased_user";

export function setSession(token: string, user: User) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(TOKEN_KEY, token);
  window.localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function clearSession() {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(TOKEN_KEY);
  window.localStorage.removeItem(USER_KEY);
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function getUser(): User | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(USER_KEY);
    return raw ? (JSON.parse(raw) as User) : null;
  } catch {
    return null;
  }
}

export function isAuthenticated(): boolean {
  return Boolean(getToken() && getUser());
}

export function homeRoute(role?: string): string {
  switch (role) {
    case "ADMIN":
      return "/dashboard/admin";
    case "DRIVER":
      return "/dashboard/driver/overview";
    default:
      return "/dashboard/overview";
  }
}

export async function refreshMe(): Promise<User> {
  const data = await get<{ user: User }>("/auth/me");
  if (typeof window !== "undefined") {
    window.localStorage.setItem(USER_KEY, JSON.stringify(data.user));
  }
  return data.user;
}

export function fullName(user: User | null): string {
  if (!user) return "";
  return `${user.first_name} ${user.last_name}`;
}