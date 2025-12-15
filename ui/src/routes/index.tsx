import SidebarInsetExample from '@/components/sidebar-example'
import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/')({ component: App })

function App() {
  return <SidebarInsetExample />
}
