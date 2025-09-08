import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { resolve } from 'path'
import fs from 'fs'

// Copy icons from main Airweave frontend
const copyIcons = () => {
    const copyIconFiles = () => {
        const srcDir = resolve(__dirname, '../../frontend/src/components/icons/apps')
        const destDir = resolve(__dirname, 'public/icons')

        // Create destination directory if it doesn't exist
        if (!fs.existsSync(destDir)) {
            fs.mkdirSync(destDir, { recursive: true })
        }

        // Copy all SVG files
        if (fs.existsSync(srcDir)) {
            const files = fs.readdirSync(srcDir)
            files.forEach(file => {
                if (file.endsWith('.svg')) {
                    fs.copyFileSync(
                        resolve(srcDir, file),
                        resolve(destDir, file)
                    )
                }
            })
            console.log(`Copied ${files.filter(f => f.endsWith('.svg')).length} icon files`)
        }
    }

    return {
        name: 'copy-icons',
        buildStart() {
            copyIconFiles()
        },
        configureServer() {
            // Also copy icons when dev server starts
            copyIconFiles()
        }
    }
}

export default defineConfig({
    plugins: [react(), copyIcons()],
    server: {
        port: 5173,
        proxy: {
            '/api': 'http://localhost:8081',
            '/ws': {
                target: 'ws://localhost:8081',
                ws: true,
            },
        },
    },
})
