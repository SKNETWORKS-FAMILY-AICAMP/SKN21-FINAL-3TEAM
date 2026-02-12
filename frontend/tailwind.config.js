/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        primary: {
          900: 'var(--color-primary-900)',
          700: 'var(--color-primary-700)',
          500: 'var(--color-primary-500)',
          300: 'var(--color-primary-300)',
          100: 'var(--color-primary-100)',
          50: 'var(--color-primary-50)',
        },
        accent: {
          700: 'var(--color-accent-700)',
          500: 'var(--color-accent-500)',
          300: 'var(--color-accent-300)',
          100: 'var(--color-accent-100)',
          50: 'var(--color-accent-50)',
        },
        surface: {
          main: 'var(--color-surface-main)',
          sub: 'var(--color-surface-sub)',
          card: 'var(--color-surface-card)',
          hover: 'var(--color-surface-hover)',
        },
        neutral: {
          main: 'var(--color-neutral-main)',
          sub: 'var(--color-neutral-sub)',
          muted: 'var(--color-neutral-muted)',
          border: 'var(--color-neutral-border)',
          divider: 'var(--color-neutral-divider)',
        },
        success: {
          DEFAULT: 'var(--color-success)',
          bg: 'var(--color-success-bg)',
        },
        warning: {
          DEFAULT: 'var(--color-warning)',
          bg: 'var(--color-warning-bg)',
        },
        error: {
          DEFAULT: 'var(--color-error)',
          bg: 'var(--color-error-bg)',
        },
        info: {
          DEFAULT: 'var(--color-info)',
          bg: 'var(--color-info-bg)',
        },
        sidebar: {
          bg: 'var(--color-sidebar-bg)',
          active: 'var(--color-sidebar-active)',
          border: 'var(--color-sidebar-border)',
          text: 'var(--color-sidebar-text)',
          'text-muted': 'var(--color-sidebar-text-muted)',
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
