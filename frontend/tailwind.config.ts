import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        garl: {
          bg: "#0a0a0f",
          surface: "#12121a",
          border: "#1e1e2e",
          accent: "#00ff88",
          "accent-dim": "#00cc6a",
          blue: "#00f3ff",
          "blue-dim": "#00c4cc",
          danger: "#ff4444",
          warning: "#ffaa00",
          muted: "#6b7280",
          text: "#e4e4e7",
        },
      },
      fontFamily: {
        mono: ["JetBrains Mono", "Fira Code", "monospace"],
      },
      animation: {
        "pulse-glow": "pulse-glow 2s ease-in-out infinite",
        "slide-up": "slide-up 0.3s ease-out",
      },
      keyframes: {
        "pulse-glow": {
          "0%, 100%": { boxShadow: "0 0 5px rgba(0, 255, 136, 0.3)" },
          "50%": { boxShadow: "0 0 20px rgba(0, 255, 136, 0.6)" },
        },
        "slide-up": {
          "0%": { transform: "translateY(10px)", opacity: "0" },
          "100%": { transform: "translateY(0)", opacity: "1" },
        },
      },
    },
  },
  plugins: [],
};

export default config;
