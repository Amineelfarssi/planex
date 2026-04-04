import type { Config } from 'tailwindcss'

export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        planex: {
          coral: '#DA7756',
          cyan: '#5B9BD5',
          surface: '#1E1E1E',
          panel: '#252526',
          border: '#3E3E3E',
          dimmed: '#666666',
        },
      },
    },
  },
  plugins: [require('@tailwindcss/typography')],
} satisfies Config
