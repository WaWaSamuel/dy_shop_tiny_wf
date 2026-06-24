/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        sidebar: {
          bg: '#211535',
          hover: '#32214f',
          active: '#4a2f73',
        },
        brand: {
          primary: '#c28fff',
          secondary: '#26e8e0',
        },
      },
    },
  },
  plugins: [],
};
