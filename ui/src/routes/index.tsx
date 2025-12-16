import { CollectionsList } from '@/components/collections-list'
import { CreateCollection } from '@/components/create-collection'
import { Shell } from '@/components/shell'
import { createFileRoute } from '@tanstack/react-router'
import * as React from 'react'

export const Route = createFileRoute('/')({ component: App })

function App() {
  const [createCollectionOpen, setCreateCollectionOpen] = React.useState(false)

  return (
    <>
      <Shell
        showNewCollectionButton
        onNewCollectionClick={() => setCreateCollectionOpen(true)}
      >
        <CollectionsList />
      </Shell>
      <CreateCollection
        open={createCollectionOpen}
        onOpenChange={setCreateCollectionOpen}
      />
    </>
  )
}
