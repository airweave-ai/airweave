import type { Config } from "tailwindcss";
import tailwindAnimate from "tailwindcss-animate";

export default {
  darkMode: ["class"],
  content: [
    "./pages/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./app/**/*.{ts,tsx}",
    "./src/**/*.{ts,tsx}",
  ],
  prefix: "",
  theme: {
    container: {
      center: true,
      padding: "2rem",
      screens: {
        "2xl": "1400px",
      },
    },
    extend: {
      colors: {
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "transparent",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",

        // Add solid background variants
        "background-solid": "hsl(var(--background-solid))",
        "background-alpha": {
          10: "hsl(var(--background-alpha-10))",
          20: "hsl(var(--background-alpha-20))",
          30: "hsl(var(--background-alpha-30))",
          40: "hsl(var(--background-alpha-40))",
          50: "hsl(var(--background-alpha-50))",
          60: "hsl(var(--background-alpha-60))",
          70: "hsl(var(--background-alpha-70))",
          80: "hsl(var(--background-alpha-80))",
          90: "hsl(var(--background-alpha-90))",
        },

        // Add solid card variant
        card: "hsl(var(--card))",
        "card-solid": "hsl(var(--card-solid))",
        "card-foreground": "hsl(var(--card-foreground))",

        // Add solid popover variant
        popover: "hsl(var(--popover))",
        "popover-solid": "hsl(var(--popover-solid))",
        "popover-foreground": "hsl(var(--popover-foreground))",

        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },

        // Brand colors
        brand: {
          lime: "hsl(var(--brand-lime))", // Tertiary Brand Color
          yellow: "hsl(var(--brand-yellow))", // Secondary Brand Color
        },

        blue: {
          DEFAULT: "hsl(var(--blue))",
          foreground: "hsl(var(--blue-foreground))",
          50: "hsl(var(--blue-50))",
          100: "hsl(var(--blue-100))",
          200: "hsl(var(--blue-200))",
          300: "hsl(var(--blue-300))",
          400: "hsl(var(--blue-400))",
          500: "hsl(var(--blue-500))",
          600: "hsl(var(--blue-600))",
          700: "hsl(var(--blue-700))",
          800: "hsl(var(--blue-800))",
          900: "hsl(var(--blue-900))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },

        // Add solid muted variant
        muted: {
          DEFAULT: "hsl(var(--muted))",
          solid: "hsl(var(--muted-solid))",
          foreground: "hsl(var(--muted-foreground))",
        },

        // Add solid accent variant
        accent: {
          DEFAULT: "hsl(var(--accent))",
          solid: "hsl(var(--accent-solid))",
          foreground: "hsl(var(--accent-foreground))",
        },

        // Add sidebar variants
        sidebar: {
          background: "hsl(var(--sidebar-background))",
          "background-solid": "hsl(var(--sidebar-background-solid))",
          foreground: "hsl(var(--sidebar-foreground))",
          primary: "hsl(var(--sidebar-primary))",
          "primary-foreground": "hsl(var(--sidebar-primary-foreground))",
          accent: "hsl(var(--sidebar-accent))",
          "accent-solid": "hsl(var(--sidebar-accent-solid))",
          "accent-foreground": "hsl(var(--sidebar-accent-foreground))",
          border: "hsl(var(--sidebar-border))",
          ring: "transparent",
        },
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      keyframes: {
        "accordion-down": {
          from: { height: "0" },
          to: { height: "var(--radix-accordion-content-height)" },
        },
        "accordion-up": {
          from: { height: "var(--radix-accordion-content-height)" },
          to: { height: "0" },
        },
        float: {
          "0%, 100%": { transform: "translateY(0)" },
          "50%": { transform: "translateY(-10px)" },
        },
        scalePulse: {
          "0%": { opacity: "0.3", transform: "translateX(-50%) scale(0.8)" },
          "50%": { opacity: "1", transform: "translateX(-50%) scale(1.2)" },
          "100%": { opacity: "0.3", transform: "translateX(-50%) scale(0.8)" },
        },
        fadeIn: {
          from: { opacity: "0", transform: "translateY(4px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        "accordion-down": "accordion-down 0.2s ease-out",
        "accordion-up": "accordion-up 0.2s ease-out",
        float: "float 3s ease-in-out infinite",
        scalePulse: "scalePulse 1.5s ease-in-out",
        "fade-in": "fadeIn 0.35s ease-out forwards",
      },
      backdropBlur: {
        xs: '2px',
      },
    },
  },
  plugins: [tailwindAnimate],
} satisfies Config;
