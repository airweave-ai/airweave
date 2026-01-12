import { defineConfig, Plugin } from 'vite'
import { devtools } from '@tanstack/devtools-vite'
import { tanstackStart } from '@tanstack/react-start/plugin/vite'
import viteReact from '@vitejs/plugin-react'
import viteTsConfigPaths from 'vite-tsconfig-paths'
import tailwindcss from '@tailwindcss/vite'
import { nitro } from 'nitro/vite'
import { promises as fs } from 'fs'
import path from 'path'

// Plugin to serve the examples directory as static files
function serveExamplesPlugin(): Plugin {
  return {
    name: 'serve-examples',
    configureServer(server) {
      server.middlewares.use(async (req, res, next) => {
        if (req.url?.startsWith('/examples/')) {
          const filePath = path.join(process.cwd(), req.url)
          try {
            const content = await fs.readFile(filePath)
            const ext = path.extname(filePath)
            const contentTypes: Record<string, string> = {
              '.html': 'text/html',
              '.js': 'application/javascript',
              '.css': 'text/css',
              '.json': 'application/json',
              '.png': 'image/png',
              '.jpg': 'image/jpeg',
              '.svg': 'image/svg+xml',
            }
            res.setHeader('Content-Type', contentTypes[ext] || 'text/plain')
            res.end(content)
          } catch {
            next()
          }
        } else {
          next()
        }
      })
    }
  }
}

const config = defineConfig({
  plugins: [
    serveExamplesPlugin(),
    devtools(),
    nitro(),
    // this is the plugin that enables path aliases
    viteTsConfigPaths({
      projects: ['./tsconfig.json'],
    }),
    tailwindcss(),
    tanstackStart(),
    viteReact(),
  ],
})

export default config
