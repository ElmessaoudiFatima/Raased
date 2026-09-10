"use client";

import { createContext, useContext } from "react";

interface ShellContextValue {
  openMobileMenu: () => void;
}

export const ShellContext = createContext<ShellContextValue>({
  openMobileMenu: () => {},
});

export const useShell = () => useContext(ShellContext);