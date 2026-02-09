/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        primary: {
          900: '#3D5164',
          700: '#56728A',
          500: '#6E87A0',
          300: '#8FA3B4',
          100: '#C8D5E2',
          50: '#E8EEF3',
        },
        accent: {
          700: '#8B7D6E',
          500: '#A89580',
          300: '#C4B49A',
          100: '#EDE5D0',
          50: '#F7F3EB',
        },
        surface: {
          main: '#F5F2EC',
          sub: '#EDE5D0',
          card: '#FFFFFF',
          hover: '#FAFAF6',
        },
        neutral: {
          main: '#2C3340',
          sub: '#6B7280',
          muted: '#9CA3AF',
          border: '#DDD8CE',
          divider: '#EDE9E0',
        },
        success: {
          DEFAULT: '#5B9A6F',
          bg: '#E8F4EC',
        },
        warning: {
          DEFAULT: '#C49A3C',
          bg: '#F5EDD0',
        },
        error: {
          DEFAULT: '#C06060',
          bg: '#F5E0E0',
        },
        info: {
          DEFAULT: '#6E87A0',
          bg: '#E8EEF3',
        },
      },
      fontFamily: {
        sans: ['Noto Sans KR', '-apple-system', 'BlinkMacSystemFont', 'sans-serif'],
        display: ['Poppins', 'sans-serif'],
      },
      borderRadius: {
        sm: '8px',
        md: '12px',
        lg: '16px',
      },
      boxShadow: {
        sm: '0 1px 3px rgba(44, 51, 64, 0.04)',
        md: '0 4px 12px rgba(44, 51, 64, 0.06)',
      },
    },
  },
  plugins: [],
};
