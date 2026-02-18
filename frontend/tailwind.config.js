/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: ["class"],
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        border: "var(--border)",
        input: "var(--input)",
        ring: "var(--ring)",
        background: "var(--background)",
        foreground: "var(--foreground)",
        primary: {
          DEFAULT: "var(--primary)",
          foreground: "var(--primary-foreground)",
          50: "var(--primary-100)",
          100: "var(--primary-100)",
          200: "var(--primary-200)",
          300: "var(--primary-300)",
          400: "var(--primary-400)",
          500: "var(--primary-500)",
          600: "var(--primary-600)",
          700: "var(--primary-700)",
          800: "var(--primary-800)",
        },
        secondary: {
          DEFAULT: "var(--secondary)",
          foreground: "var(--secondary-foreground)",
        },
        destructive: {
          DEFAULT: "var(--destructive)",
          foreground: "var(--destructive-foreground)",
        },
        muted: {
          DEFAULT: "var(--muted)",
          foreground: "var(--muted-foreground)",
        },
        accent: {
          DEFAULT: "var(--accent)",
          foreground: "var(--accent-foreground)",
        },
        popover: {
          DEFAULT: "var(--popover)",
          foreground: "var(--popover-foreground)",
        },
        card: {
          DEFAULT: "var(--card)",
          foreground: "var(--card-foreground)",
        },
        sidebar: {
          DEFAULT: "var(--sidebar-background)",
          foreground: "var(--sidebar-foreground)",
          primary: "var(--sidebar-primary)",
          "primary-foreground": "var(--sidebar-primary-foreground)",
          accent: "var(--sidebar-accent)",
          "accent-foreground": "var(--sidebar-accent-foreground)",
          border: "var(--sidebar-border)",
          ring: "var(--sidebar-ring)",
        },
        // Modern Blue design system
        eco: {
          primary: "var(--primary-600)",
          secondary: "var(--primary-400)",
          earth: "var(--primary-300)",
          sky: "var(--primary-300)",
          background: "var(--bg-main)",
        },
        // Unified status colors (Blue Gradient)
        status: {
          success: "var(--status-good)",
          warning: "var(--status-warning)",
          error: "var(--status-critical)",
          info: "var(--primary-400)",
        },
        // Chart Palette
        chart: {
          green: "var(--chart-green)",
          blue: "var(--chart-blue)",
          "green-light": "var(--chart-green-light)",
          brown: "var(--chart-brown)",
          "green-dark": "var(--chart-green-dark)",
          grid: "var(--chart-grid)",
          background: "var(--chart-bg)",
        },
        // Pie Palette
        pie: {
          1: "var(--pie-1)",
          2: "var(--pie-2)",
          3: "var(--pie-3)",
          4: "var(--pie-4)",
          5: "var(--pie-5)",
        },
        // Legacy/Compatibility
        brand: {
          DEFAULT: "var(--primary-600)",
          50: "var(--primary-100)",
          600: "var(--primary-600)",
        },
        // Wise Theme Colors
        wise: {
          lime: '#9FE870',    // Bright Brand Color
          forest: '#163300',  // Primary Button/Text
          bg: '#F2F5F7',      // Main App Background
          sage: '#5F6F62',    // Borders & Sub-text
          foam: '#E1F0D6',    // Hovers & Accents
        },
        nature: {
          bg: '#F0FDF4',       // Light Green BG (Mint)
          light: '#DCFCE7',    // Hover Mint
          fern: '#22C55E',     // Standard Green
          teal: '#14B8A6',     // Cool Green
          sun: '#FACC15',      // Yellow Accent
          earth: '#D97706',    // Amber Accent
        },
      },
      borderRadius: {
        xl: "calc(var(--radius) + 4px)",
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
        xs: "calc(var(--radius) - 6px)",
      },
      boxShadow: {
        xs: "0 1px 2px 0 rgb(0 0 0 / 0.05)",
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
        "caret-blink": {
          "0%,70%,100%": { opacity: "1" },
          "20%,50%": { opacity: "0" },
        },
      },
      animation: {
        "accordion-down": "accordion-down 0.2s ease-out",
        "accordion-up": "accordion-up 0.2s ease-out",
        "caret-blink": "caret-blink 1.25s ease-out infinite",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
}