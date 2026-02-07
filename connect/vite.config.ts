import { defineConfig, Plugin } from 'vite'
import { devtools } from '@tanstack/devtools-vite'
import { tanstackStart } from '@tanstack/react-start/plugin/vite'
import viteReact from '@vitejs/plugin-react'
import viteTsConfigPaths from 'vite-tsconfig-paths'
import tailwindcss from '@tailwindcss/vite'
import { nitro } from 'nitro/vite'
import { promises as fs } from 'fs'
import path from 'path'

// Path to frontend icons (source of truth)
const FRONTEND_ICONS_PATH = path.resolve(__dirname, '../frontend/src/components/icons/apps')

// Plugin to copy and serve app icons from the frontend package
function copyAppIconsPlugin(): Plugin {
  return {
    name: 'copy-app-icons',
    // Serve icons from frontend during development
    configureServer(server) {
      server.middlewares.use(async (req, res, next) => {
        if (req.url?.startsWith('/icons/apps/')) {
          const iconName = req.url.replace('/icons/apps/', '')
          const iconPath = path.resolve(FRONTEND_ICONS_PATH, iconName)
          // Prevent path traversal - ensure resolved path is within allowed directory
          if (!iconPath.startsWith(FRONTEND_ICONS_PATH + path.sep)) {
            res.statusCode = 403
            res.end('Forbidden')
            return
          }
          try {
            const content = await fs.readFile(iconPath)
            res.setHeader('Content-Type', 'image/svg+xml')
            res.end(content)
          } catch {
            next()
          }
        } else {
          next()
        }
      })
    },
    // Copy icons to output during build
    async writeBundle(options) {
      const outputDir = options.dir || '.output/public'
      const targetDir = path.join(outputDir, 'icons/apps')

      // Create target directory
      await fs.mkdir(targetDir, { recursive: true })

      // Copy all SVG files from frontend icons
      const files = await fs.readdir(FRONTEND_ICONS_PATH)
      for (const file of files) {
        if (file.endsWith('.svg')) {
          const src = path.join(FRONTEND_ICONS_PATH, file)
          const dest = path.join(targetDir, file)
          await fs.copyFile(src, dest)
        }
      }
    }
  }
}

// Plugin to serve the examples directory as static files
function serveExamplesPlugin(): Plugin {
  const examplesDir = path.resolve(process.cwd(), 'examples')
  return {
    name: 'serve-examples',
    configureServer(server) {
      server.middlewares.use(async (req, res, next) => {
        if (req.url?.startsWith('/examples/')) {
          const relativePath = req.url.replace('/examples/', '')
          const filePath = path.resolve(examplesDir, relativePath)
          // Prevent path traversal - ensure resolved path is within examples directory
          if (!filePath.startsWith(examplesDir + path.sep)) {
            res.statusCode = 403
            res.end('Forbidden')
            return
          }
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
    copyAppIconsPlugin(),
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
