import { Outlet, createRootRouteWithContext } from '@tanstack/react-router';
import { TanStackRouterDevtoolsPanel } from '@tanstack/react-router-devtools';
import { ReactQueryDevtoolsPanel } from '@tanstack/react-query-devtools';
import { TanStackDevtools } from '@tanstack/react-devtools';
import { formDevtoolsPlugin } from '@tanstack/react-form-devtools';
import type { RouterContext } from '@/app/router/context';

import '@/app/styles/index.css';

export const Route = createRootRouteWithContext<RouterContext>()({
  component: RootComponent,
});

function RootComponent() {
  return (
    <>
      <Outlet />
      <TanStackDevtools
        config={{
          position: 'bottom-right',
        }}
        plugins={[
          { name: 'TanStack Query', render: <ReactQueryDevtoolsPanel /> },
          {
            name: 'TanStack Router',
            render: <TanStackRouterDevtoolsPanel />,
          },
          formDevtoolsPlugin(),
        ]}
      />
    </>
  );
}
