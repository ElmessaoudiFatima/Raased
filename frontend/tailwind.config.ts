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
          navy: "#1a1a3d",
          teal: "#0d7377",
          alert: "#d64541",
        },
      },
    },
  },
  plugins: [],
};

export default config;
