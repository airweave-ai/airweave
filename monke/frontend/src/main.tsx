import React from 'react'
import { createRoot } from 'react-dom/client'
import './main.css'
import { Toaster } from 'sonner'

import { App } from './ui/App'

createRoot(document.getElementById('root')!).render(
    <React.StrictMode>
        <Toaster richColors position="top-right" />
        <App />
    </React.StrictMode>
)
