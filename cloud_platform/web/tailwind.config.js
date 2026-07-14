/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        bg: '#080d13',
        surface: '#101821',
        panel: '#151f2b',
        'panel-2': '#1b2633',
        'panel-3': '#202d3d',
        line: '#263241',
        'line-soft': 'rgba(147,164,186,0.16)',
        text: '#eef4ff',
        muted: '#8997a8',
        'muted-2': '#667386',
        accent: '#e88b45',
        cyan: '#5baec7',
        success: '#58b98e',
        danger: '#d85b64',
        warn: '#95a5a6',
      },
      fontFamily: {
        sans: ['Inter', 'PingFang SC', 'Microsoft YaHei', 'Arial', 'sans-serif'],
      },
    },
  },
  plugins: [],
};
