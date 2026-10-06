/// <reference types="vitest/config" />
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// En desarrollo, /api y /admin se reenvían a Django: el navegador ve un solo origen,
// así funcionan la cookie de sesión y el token CSRF sin configurar CORS.
// Puertos propios (8010/5180) para convivir con otros proyectos que usan 8000/5173.
const backend = process.env.BACKEND_URL ?? 'http://localhost:8010'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5180,
    strictPort: true, // si está ocupado, falla en vez de moverse (CSRF solo acepta 5180)
    proxy: {
      '/api': { target: backend, changeOrigin: true },
      '/admin': { target: backend, changeOrigin: true },
      '/static': { target: backend, changeOrigin: true },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    css: false,
  },
})
