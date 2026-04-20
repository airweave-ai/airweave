import * as React from 'react';
import { getRouteApi } from '@tanstack/react-router';
import { CreateApiKeyDialog } from '@/features/api-keys';

const routeApi = getRouteApi('/_authenticated/_app/api-keys/create');

export function ApiKeysCreatePage() {
  const navigate = routeApi.useNavigate();

  const handleClose = React.useCallback(() => {
    void navigate({
      to: '/api-keys',
      viewTransition: true,
    });
  }, [navigate]);

  return <CreateApiKeyDialog onClose={handleClose} />;
}
