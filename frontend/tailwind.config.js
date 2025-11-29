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
        brand: {
          500: '#3b82f6',
          600: '#2563eb',
          700: '#1d4ed8',
        },
      },
      boxShadow: {
        card: '0 10px 35px rgba(0, 0, 0, 0.35)',
      },
      backgroundImage: {
        'mountain-hero': "linear-gradient(to bottom, rgba(0,0,0,0.6), rgba(0,0,0,0.75)), url('https://images.unsplash.com/photo-1508261306217-011c10660dc6?auto=format&fit=crop&w=1600&q=80')",
      },
    },
  },
  plugins: [],
}
