"use client";

import React, { createContext, useCallback, useContext, useRef, useState } from "react";
import { CheckCircle2, Info, XCircle } from "lucide-react";

type ToastType = "success" | "error" | "info";

interface ToastItem {
  id: number;
  type: ToastType;
  message: string;
}

interface ToastContextValue {
  notify: (message: string, type?: ToastType) => void;
}

const ToastContext = createContext<ToastContextValue>({ notify: () => {} });

export function useToast() {
  return useContext(ToastContext);
}

const styles: Record<ToastType, { bar: string; icon: React.ReactNode }> = {
  success: { bar: "bg-emerald-500", icon: <CheckCircle2 className="h-5 w-5 text-emerald-500" /> },
  error: { bar: "bg-raased-alert", icon: <XCircle className="h-5 w-5 text-raased-alert" /> },
  info: { bar: "bg-raased-teal", icon: <Info className="h-5 w-5 text-raased-teal" /> },
};

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const idRef = useRef(0);

  const notify = useCallback((message: string, type: ToastType = "success") => {
    const id = ++idRef.current;
    setToasts((t) => [...t, { id, type, message }]);
    setTimeout(() => {
      setToasts((t) => t.filter((x) => x.id !== id));
    }, 4500);
  }, []);

  return (
    <ToastContext.Provider value={{ notify }}>
      {children}
      <div className="pointer-events-none fixed bottom-5 right-5 z-[200] flex w-80 flex-col gap-2">
        {toasts.map((t) => (
          <div
            key={t.id}
            className="pointer-events-auto relative flex items-start gap-3 overflow-hidden rounded-xl border border-slate-200 bg-white p-3.5 pr-8 shadow-xl"
          >
            <span className={`absolute left-0 top-0 h-full w-1 ${styles[t.type].bar}`} />
            {styles[t.type].icon}
            <p className="text-sm font-medium text-slate-700">{t.message}</p>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}