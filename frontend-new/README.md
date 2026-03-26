# frontend-new

`frontend-new/` is the new frontend application, currently WIP. It uses TanStack Router file-based routing with a lightweight `app/pages/features/shared` structure.

## Structure

```text
src/
  app/
    layouts/      # app-wide chrome (AppShell, AppSidebar)
    pages/        # screen composition layer
    providers/    # app-wide providers
    router/       # router setup + typed router context
    styles/       # global app styles
  routes/         # TanStack file routes only
  features/       # reusable product/domain slices
  shared/         # infra, auth, generated api client, ui primitives, config
  main.tsx        # React/Vite entrypoint only
  routeTree.gen.ts
```

## Where code goes

- `routes/`: route definitions only. Keep files thin - `beforeLoad`, `loader`, `validateSearch`, then render an app page.
- `app/pages/`: screen composition. Pages compose reusable feature blocks and shared UI for a single screen.
- `app/layouts/`: app-wide shell and navigation that wrap many pages.
- `app/providers/` and `app/router/`: app bootstrap, router context, and global wiring.
- `features/`: reusable domain/product slices like `collections`, `usage`, and `organization-events`. Export a small public API from the feature root `index.ts`.
- `shared/`: cross-cutting infrastructure and primitives. Main homes:
  - `shared/api/`: API client, TanStack Query client, and generated OpenAPI client/query options in `shared/api/generated/`
  - `shared/auth/`: `AuthProvider`, `useAuth`, and auth integration helpers
  - `shared/config/`: environment config
  - `shared/ui/`: low-level UI primitives
  - `shared/tailwind/`: Tailwind helpers like `cn`

## Working rules

- Add a new screen by creating `app/pages/<screen>/` and a matching file route in `routes/`.
- Compose multiple features in `app/pages/`, not inside another feature.
- Avoid feature-to-feature imports. If multiple features need to work together, do that in a page.
- Use TanStack Query for server state. Generated query options live in `shared/api/generated/`; add thin feature adapters only when they make the calling code clearer.
- Keep `main.tsx` dumb; app composition belongs in `app/`.
- Use barrel files selectively: `app/`, `app/router/`, `shared/auth/`, `shared/api/`, and feature roots are fine. Avoid giant catch-all barrels like `shared/index.ts`.

## shadcn/ui

To add a component:

```bash
npx shadcn@latest add button
```

shadcn is configured to place UI primitives in `src/shared/ui`.

Example import:

```tsx
import { Button } from '@/shared/ui/button';
```
