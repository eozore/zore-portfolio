import type { Config } from 'tailwindcss';

const config: Config = {
  content: [
    './src/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        // Light mode — paleta éozoré: laranja, bege, preto/cinza
        'bg-deep': '#f8f7f4',
        'bg-surface': '#ffffff',
        'bg-elevated': '#f1f0ed',
        primary: '#e67e22',
        glow: '#f5a962',
        'accent-data': '#d35400',
        'accent-success': '#16a34a',
        'accent-warn': '#d97706',
        'text-main': '#1e1e1e',
        'text-muted': '#6b6b6b',
        border: 'rgba(30,30,30,0.1)',
        // Fallbacks
        secondary: '#ffffff',
        accent: '#f5a962',
        background: '#f8f7f4',
        'text-light': '#6b6b6b',
      },
      fontFamily: {
        sans: ['var(--font-inter)', 'Inter', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'SF Mono', 'monospace'],
      },
      borderRadius: {
        card: '20px',
        'card-lg': '24px',
      },
      maxWidth: {
        container: '1140px',
      },
      boxShadow: {
        glow: '0 0 20px rgba(230,126,34,0.3)',
        'glow-sm': '0 0 10px rgba(230,126,34,0.2)',
        'glow-cyan': '0 0 20px rgba(245,169,98,0.3)',
      },
      animation: {
        'pulse-slow': 'pulse 4s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'glow-border': 'glow-border 3s ease-in-out infinite alternate',
        blink: 'blink 1s step-end infinite',
        float: 'float 6s ease-in-out infinite',
      },
      keyframes: {
        'glow-border': {
          '0%': { borderColor: 'rgba(230,126,34,0.15)' },
          '100%': { borderColor: 'rgba(230,126,34,0.4)' },
        },
        blink: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0' },
        },
        float: {
          '0%, 100%': { transform: 'translateY(0px)' },
          '50%': { transform: 'translateY(-10px)' },
        },
      },
    },
  },
  plugins: [],
};

export default config;
