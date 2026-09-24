/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,jsx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#effcf6',
          100: '#c9f7e5',
          200: '#94eecb',
          300: '#5fe0b3',
          400: '#2cc99a',
          500: '#0f9d76', // primary teal/green
          600: '#0a7f60',
          700: '#08654d',
          800: '#0a4f3e',
          900: '#0a4234',
        },
        surface: {
          DEFAULT: '#ffffff',
          muted: '#f6f8f7',
        },
        ink: {
          900: '#111827',
          700: '#374151',
          500: '#6b7280',
          300: '#d1d5db',
        },
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
