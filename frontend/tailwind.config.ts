import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        raased: {
          navy: "#0f1733",
          "navy-800": "#16214a",
          teal: "#0d7377",
          "teal-light": "#12b3a8",
          alert: "#d64541",
          bg: "#f4f7fc",
        },
        figma: {
          bg: "#0a101d",
          "bg-dark": "#070a12",
          card: "#0f172a",
          "card-hover": "#131f37",
          border: "#1e293b",
          "border-focus": "#3b82f6",
          blue: "#2563eb",
          "blue-hover": "#1d4ed8",
          "blue-light": "#3b82f6",
          cyan: "#06b6d4",
          text: "#f8fafc",
          muted: "#94a3b8",
        },
      },
      boxShadow: {
        "figma-glow": "0 0 25px -5px rgba(37, 99, 235, 0.4)",
        "figma-card": "0 10px 30px -10px rgba(0, 0, 0, 0.5), 0 0 1px 1px rgba(255, 255, 255, 0.05)",
      },
    },
  },
  plugins: [],
};

export default config;