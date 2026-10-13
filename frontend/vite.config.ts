import react from '@vitejs/plugin-react'
// Imported from 'vitest/config', not plain 'vite' -- that module's
// UserConfigExport type doesn't know about the `test` key at all, which
// is exactly the TS2769 error this swap fixes. Vitest's defineConfig
// re-exports Vite's own config type merged with its own `test` block, so
// the server/plugins config below is unchanged/still fully valid.
import { defineConfig } from 'vitest/config'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Reads VITE_PORT if set, otherwise falls back to Vite's own default
    // (5173) -- running `npm run dev` with no env var set behaves exactly
    // as before this change. Lets a second, independent dev server
    // instance be launched on a different port (e.g. for isolated
    // verification) without colliding with an already-running instance on
    // 5173, by setting VITE_PORT before invoking npm run dev.
    port: process.env.VITE_PORT ? Number(process.env.VITE_PORT) : 5173,
    // Vite's dev server rejects requests whose Host header it doesn't
    // recognize (DNS-rebinding protection), which blocks a public tunnel
    // (zrok/ngrok) from reaching it with a 403 by default. Allow the
    // current zrok frontend tunnel host explicitly. Update this value (or
    // add another entry) whenever the tunnel is restarted and gets a new
    // subdomain -- zrok's free tier does not keep the same hostname across
    // restarts.
    allowedHosts: ['0gfx2ge0v27b.shares.zrok.io'],
  },
  // Vitest config lives alongside the Vite dev-server config -- same file,
  // same `defineConfig`, standard Vitest setup. `environment: 'jsdom'` is
  // required for React Testing Library (document/window must exist).
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.js'],
  },
})
