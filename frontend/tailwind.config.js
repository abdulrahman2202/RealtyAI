/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        teal: {
          900: "#12544f",
          800: "#14625c",
          700: "#1a7a74",
        },
        yellow: {
          warm: "#FDF4D2",
        },
        orange: {
          accent: "#FF9100",
        },
        ivory: {
          50: "#FBF9F4",
          100: "#F5F1E8",
          200: "#EDE3CB",
        },
        neutral: {
          900: "#2A2929",
          800: "#444444",
          700: "#666666",
          600: "#888888",
          500: "#AAAAAA",
          400: "#CCCCCC",
          100: "#F5F5F5",
          50: "#FAFAFA",
        },
      },
      fontFamily: {
        serif: ["var(--font-serif)", "Georgia", "serif"],
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
      },
      typography: {
        DEFAULT: {
          css: {
            maxWidth: "none",
            color: "#2A2929",
            a: {
              color: "#12544f",
              textDecoration: "none",
              "&:hover": {
                color: "#FF9100",
                textDecoration: "underline",
              },
            },
          },
        },
      },
      animation: {
        "fade-in": "fadeIn 0.4s ease-out forwards",
        "slide-up": "slideUp 0.4s ease-out forwards",
        "pulse-soft": "pulseSoft 2s ease-in-out infinite",
      },
      keyframes: {
        fadeIn: {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        slideUp: {
          "0%": { opacity: "0", transform: "translateY(10px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        pulseSoft: {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.6" },
        },
      },
    },
  },
  plugins: [],
};
