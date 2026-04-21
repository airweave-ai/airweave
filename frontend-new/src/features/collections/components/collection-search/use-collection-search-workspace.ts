import * as React from 'react';
import { createCollectionSearchRequest } from '../../lib/collection-search-request';
import {
  getCollectionSearchFormOptions,
  useCollectionSearchForm,
} from './collection-search-form-hook';
import { useCollectionSearchTiers } from './use-collection-search-tiers';
import type { CollectionSearchFormValues } from '../../lib/collection-search-model';
import type { CollectionSearchRequest } from '../../lib/collection-search-request';
import type { CollectionSearchTiers } from './use-collection-search-tiers';

export function useCollectionSearchWorkspace({
  collectionId,
}: {
  collectionId: string;
}) {
  const tiers = useCollectionSearchTiers({ collectionId });
  const onSubmit = React.useCallback(
    (values: CollectionSearchFormValues) => {
      submitCollectionSearchRequest(
        tiers,
        createCollectionSearchRequest({
          collectionId,
          values,
        }),
      );
    },
    [collectionId, tiers],
  );
  const form = useCollectionSearchForm(
    getCollectionSearchFormOptions({ onSubmit }),
  );

  return {
    form,
    tiers,
  };
}

export type CollectionSearchWorkspaceForm = ReturnType<
  typeof useCollectionSearchWorkspace
>['form'];

function submitCollectionSearchRequest(
  tiers: CollectionSearchTiers,
  request: CollectionSearchRequest,
) {
  switch (request.tier) {
    case 'classic':
      tiers.classic.submit(request);
      break;
    case 'instant':
      tiers.instant.submit(request);
      break;
    case 'agentic':
      tiers.agentic.submit(request);
      break;
  }
}
