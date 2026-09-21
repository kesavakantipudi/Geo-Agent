import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#eefbf4",
          100: "#d6f4e3",
          200: "#b0e8cc",
          300: "#7dd6ae",
          400: "#47bd8b",
          500: "#20a171",
          600: "#12825b",
          700: "#0f684b",
          800: "#0e523d",
          900: "#0c4434",
        },
      },
    },
  },
  plugins: [],
};

export default config;