import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://8.140.28.233:8000',
        changeOrigin: true,
      },
      '/evidence': {
        target: 'http://8.140.28.233',
        changeOrigin: true,
      },
    },
  },
});
