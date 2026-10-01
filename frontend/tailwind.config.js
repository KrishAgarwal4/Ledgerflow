/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        stripe: {
          50: '#F4F5FB',
          100: '#E6E8F6',
          200: '#CCD1EE',
          300: '#99A3E0',
          400: '#7A85D6',
          500: '#635BFF', // Stripe core blurple
          600: '#5347E8',
          700: '#4334C4',
          800: '#34259A',
          900: '#23186F',
        },
        surface: {
          base: '#0B0F19',
          card: '#111827',
          elevated: '#1F2937',
          subtle: '#374151',
          border: '#1E293B',
          'border-subtle': '#334155'
        }
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'Menlo', 'monospace'],
      },
    },
  },
  plugins: [],
}
