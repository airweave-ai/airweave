import * as React from 'react'

export interface CollectionData {
  name: string
  id: string
  randomId: string
}

export function useCollectionData(collectionName: string): CollectionData {
  const randomId = React.useRef(Math.random().toString(36).substring(2, 15))

  return React.useMemo(
    () => ({
      name: collectionName,
      id:
        collectionName
          ?.toLowerCase()
          .replace(/ /g, '-')
          .replace(/[^a-z0-9-]/g, '')
          .substring(0, 10) || 'your-collection',
      randomId: randomId.current,
    }),
    [collectionName],
  )
}
