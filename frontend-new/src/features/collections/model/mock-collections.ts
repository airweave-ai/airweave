export type CollectionStatus = 'Synced' | 'Paused' | 'Draft';

export type Collection = {
  id: string;
  name: string;
  sourceCount: number;
  status: CollectionStatus;
  updatedAt: string;
};

export const mockCollections: Array<Collection> = [
  {
    id: 'product-docs',
    name: 'Product Docs',
    sourceCount: 4,
    status: 'Synced',
    updatedAt: '5 min ago',
  },
  {
    id: 'support-hub',
    name: 'Support Hub',
    sourceCount: 2,
    status: 'Synced',
    updatedAt: '18 min ago',
  },
  {
    id: 'sales-playbooks',
    name: 'Sales Playbooks',
    sourceCount: 3,
    status: 'Paused',
    updatedAt: '1 hour ago',
  },
  {
    id: 'ops-runbooks',
    name: 'Ops Runbooks',
    sourceCount: 1,
    status: 'Draft',
    updatedAt: 'Yesterday',
  },
];
