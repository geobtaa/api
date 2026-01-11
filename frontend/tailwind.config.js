/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}', './app/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        brand: 'rgb(var(--color-primary) / <alpha-value>)',
        'brand-active': 'rgb(var(--color-active) / <alpha-value>)',
      },
    },
  },
  plugins: [
    require('@tailwindcss/typography'),
  ],
};