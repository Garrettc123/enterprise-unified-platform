import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: false,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
  build: {
    target: 'ES2020',
    minify: 'terser',
    sourcemap: false,
    chunkSizeWarningLimit: 1000,
  },
  test: {
    // Node's built-in test suite runs separately via node --test.
    exclude: ['tests/**/*.test.mjs', '**/node_modules/**', '**/dist/**'],
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/test/setup.ts',
  },
})
