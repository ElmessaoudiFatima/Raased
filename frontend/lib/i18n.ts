"use client";

import { useEffect, useState } from "react";

export type Language = "FR" | "EN" | "AR";

export interface Translations {
  welcome: string;
  subtitle: string;
  emailLabel: string;
  emailPlaceholder: string;
  passwordLabel: string;
  passwordPlaceholder: string;
  forgotPassword: string;
  signIn: string;
  signingIn: string;
  dontHaveAccount: string;
  signUpLink: string;
  loginError: string;
  backToLogin: string;
  brandTagline: string;
}

export const DICTIONARY: Record<Language, Translations> = {
  FR: {
    welcome: "Bienvenue sur Raased",
    subtitle: "Connectez-vous pour accéder à votre espace de pilotage",
    emailLabel: "Adresse e-mail",
    emailPlaceholder: "votre@entreprise.com",
    passwordLabel: "Mot de passe",
    passwordPlaceholder: "••••••••",
    forgotPassword: "Mot de passe oublié ?",
    signIn: "Se connecter",
    signingIn: "Connexion en cours...",
    dontHaveAccount: "Première fois sur Raased ?",
    signUpLink: "Créer un compte entreprise",
    loginError: "Connexion impossible. Vérifiez vos identifiants.",
    backToLogin: "Retour à la connexion",
    brandTagline: "Observateur des corridors logistiques",
  },
  EN: {
    welcome: "Welcome to Raased",
    subtitle: "Sign in to your account to continue",
    emailLabel: "Email address",
    emailPlaceholder: "your@company.com",
    passwordLabel: "Password",
    passwordPlaceholder: "••••••••",
    forgotPassword: "Forgot password?",
    signIn: "Sign In",
    signingIn: "Signing in...",
    dontHaveAccount: "Don't have an account?",
    signUpLink: "Create company account",
    loginError: "Sign-in failed. Please check your credentials.",
    backToLogin: "Back to login",
    brandTagline: "Logistics Corridor Resilience Agent",
  },
  AR: {
    welcome: "مرحباً بكم في راصد",
    subtitle: "سجل الدخول إلى حسابك للوصول إلى منصة القيادة",
    emailLabel: "البريد الإلكتروني",
    emailPlaceholder: "name@company.com",
    passwordLabel: "كلمة المرور",
    passwordPlaceholder: "••••••••",
    forgotPassword: "نسيت كلمة المرور؟",
    signIn: "تسجيل الدخول",
    signingIn: "جاري تسجيل الدخول...",
    dontHaveAccount: "ليس لديك حساب على راصد؟",
    signUpLink: "إنشاء حساب شركة",
    loginError: "تعذر تسجيل الدخول. يرجى التحقق من بياناتك.",
    backToLogin: "العودة لتسجيل الدخول",
    brandTagline: "وكيل مرونة الممرات اللوجستية",
  },
};

const STORAGE_KEY = "raased_lang";

export function useLanguage() {
  const [lang, setLang] = useState<Language>("FR");

  useEffect(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY) as Language | null;
      if (saved && (saved === "FR" || saved === "EN" || saved === "AR")) {
        setLang(saved);
      }
    } catch {}
  }, []);

  const changeLanguage = (newLang: Language) => {
    setLang(newLang);
    try {
      localStorage.setItem(STORAGE_KEY, newLang);
      document.documentElement.lang = newLang.toLowerCase();
      document.documentElement.dir = newLang === "AR" ? "rtl" : "ltr";
    } catch {}
  };

  const t = DICTIONARY[lang];
  const isRTL = lang === "AR";

  return { lang, changeLanguage, t, isRTL };
}
