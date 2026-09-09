import axios from "axios";

export const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

export const BACKEND_URL = API_URL.replace(/\/api\/?$/, "");

export interface ApiErrorData {
  error?: string;
  message?: string;
  detail?: string | Array<{ msg?: string }>;
}

export class ApiError extends Error {
  status: number;
  data: ApiErrorData;

  constructor(status: number, data: ApiErrorData) {
    let msg = "Une erreur est survenue";
    if (typeof data?.detail === "string") {
      msg = data.detail;
    } else if (Array.isArray(data?.detail) && data.detail[0]?.msg) {
      msg = data.detail[0].msg;
    } else if (data?.error) {
      msg = data.error;
    } else if (data?.message) {
      msg = data.message;
    }
    super(msg);
    this.status = status;
    this.data = data;
  }
}

export const api = axios.create({
  baseURL: API_URL,
  headers: { "Content-Type": "application/json" },
});

api.interceptors.request.use((config) => {
  const token =
    typeof window !== "undefined" ? window.localStorage.getItem("raased_token") : null;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      if (typeof window !== "undefined") {
        const onAuthPages =
          window.location.pathname.startsWith("/login") ||
          window.location.pathname.startsWith("/forgot-password") ||
          window.location.pathname.startsWith("/register") ||
          window.location.pathname.startsWith("/set-password");
        if (!onAuthPages) {
          window.localStorage.removeItem("raased_token");
          window.localStorage.removeItem("raased_user");
          window.location.href = "/login";
        }
      }
    }
    return Promise.reject(
      new ApiError(
        error.response?.status || 500,
        error.response?.data || { error: "Erreur navigateur" }
      )
    );
  }
);

export async function get<T>(url: string, params?: Record<string, unknown>): Promise<T> {
  const res = await api.get<T>(url, { params });
  return res.data;
}

export async function post<T>(url: string, body?: unknown): Promise<T> {
  const res = await api.post<T>(url, body);
  return res.data;
}

export async function patch<T>(url: string, body?: unknown): Promise<T> {
  const res = await api.patch<T>(url, body);
  return res.data;
}

export async function del<T>(url: string): Promise<T> {
  const res = await api.delete<T>(url);
  return res.data;
}


export async function upload<T>(
  url: string,
  formData: FormData,
  onProgress?: (pct: number) => void
): Promise<T> {
  const res = await api.post<T>(url, formData, {
    headers: { "Content-Type": "multipart/form-data" },
    onUploadProgress: (e) => {
      if (onProgress && e.total) onProgress(Math.round((e.loaded * 100) / e.total));
    },
  });
  return res.data;
}

export async function openPdfWithAuth(url: string): Promise<void> {
  const res = await api.get(url, { responseType: "blob" });
  const blobUrl = URL.createObjectURL(res.data);
  window.open(blobUrl, "_blank");
}