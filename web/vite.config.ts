import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { fileURLToPath, URL } from 'node:url'
import { rm } from 'node:fs/promises'
import path from 'node:path'

/** Vendor chunk groups for production bundle splitting. */
const VENDOR_CHUNKS: Record<string, readonly string[]> = {
  'vendor-react': ['react', 'react-dom', 'react-router'],
  'vendor-ui': ['@base-ui/react', 'cmdk-base', 'class-variance-authority', 'clsx', 'tailwind-merge', 'lucide-react'],
  'vendor-charts': ['recharts'],
  'vendor-flow': ['@xyflow/react', '@dagrejs/dagre', 'd3-force'],
  'vendor-editor': ['@codemirror/commands', '@codemirror/lang-json', '@codemirror/lang-yaml', '@codemirror/language', '@codemirror/state', '@codemirror/view'],
  'vendor-motion': ['framer-motion'],
  'vendor-dnd': ['@dnd-kit/core', '@dnd-kit/sortable', '@dnd-kit/utilities'],
  'vendor-state': ['zustand', '@tanstack/react-query', 'axios'],
} as const

function manualChunks(id: string): string | undefined {
  if (!id.includes('node_modules')) return undefined
  for (const [chunk, packages] of Object.entries(VENDOR_CHUNKS)) {
    if (packages.some((pkg) => id.includes(`node_modules/${pkg}`))) {
      return chunk
    }
  }
  return undefined
}

export default defineConfig(async () => {
  const plugins = [
    react(),
    tailwindcss(),
    {
      name: 'remove-msw-worker',
      apply: 'build' as const,
      closeBundle: async () => {
        await rm(path.resolve(__dirname, 'dist', 'mockServiceWorker.js'), { force: true })
      },
    },
  ]

  if (process.env.VITE_ANALYZE) {
    const { visualizer } = await import('rollup-plugin-visualizer')
    plugins.push(visualizer({ filename: 'stats.html', open: true }) as ReturnType<typeof react>)
  }

  return {
    plugins,
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url)),
      },
    },
    server: {
      port: 5173,
      proxy: {
        '/api': {
          target: 'http://localhost:3001',
          changeOrigin: true,
          ws: true,
        },
      },
    },
    preview: {
      port: 4173,
      strictPort: true,
    },
    build: {
      rollupOptions: {
        output: {
          manualChunks,
        },
      },
    },
  }
})
