/// <reference types="vitest" />
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import path from 'node:path'

/**
 * Vitest config for the Next.js 16 frontend.
 *
 * - jsdom environment so React components have a DOM
 * - jest-dom matchers loaded via setup file
 * - `@/*` path alias mirrors tsconfig
 * - css disabled — we don't render Tailwind in tests, only behavior
 */
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./vitest.setup.ts'],
    globals: true,
    css: false,
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
    exclude: ['node_modules', '.next'],
  },
})
