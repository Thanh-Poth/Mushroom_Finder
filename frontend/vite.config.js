import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  // Écoute sur localhost uniquement ; le conteneur Docker passe --host lui-même.
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': { target: process.env.API_TARGET || 'http://localhost:8000', changeOrigin: true },
    },
  },
})
