/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./app/**/*.{ts,tsx}', './components/**/*.{ts,tsx}', './lib/**/*.{ts,tsx}'],
  presets: [require('nativewind/preset')],
  theme: {
    extend: {
      colors: {
        brand: {
          DEFAULT: '#2f95dc',
          dark: '#1b6ea8',
        },
        bg: {
          light: '#ffffff',
          dark: '#000000',
        },
      },
      borderRadius: {
        xl: '14px',
        '2xl': '20px',
      },
    },
  },
  plugins: [],
};

