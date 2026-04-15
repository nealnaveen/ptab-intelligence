import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          50:  "#f0f4ff",
          100: "#e0e9ff",
          500: "#3b6fd4",
          600: "#2c5ab8",
          700: "#1e3f8a",
          900: "#0f1f4a",
        },
      },
    },
  },
  plugins: [],
};
export default config;
