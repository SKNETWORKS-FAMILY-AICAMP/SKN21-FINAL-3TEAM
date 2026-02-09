/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // 디자인 시스템 컬러
        background: {
          light: '#FFFEF5',
          DEFAULT: '#FAF9F6',
        },
        primary: {
          DEFAULT: '#3B82F6',
          50: '#EFF6FF',
          100: '#DBEAFE',
          500: '#3B82F6',
          600: '#2563EB',
          700: '#1D4ED8',
        },
        accent: {
          DEFAULT: '#8B5CF6',
          50: '#F5F3FF',
          500: '#8B5CF6',
          600: '#7C3AED',
        },
      },
    },
  },
  plugins: [],
}
