import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev-режим: vite (5173) проксирует /api на FastAPI (8700)
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8700',
        changeOrigin: true,
      },
    },
  },
})
