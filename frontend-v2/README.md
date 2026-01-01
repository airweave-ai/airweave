# Airweave Frontend v2

Modern React frontend for the Airweave platform, built with TanStack Start and a comprehensive UI component library.

## Tech Stack

- **Framework**: [TanStack Start](https://tanstack.com/start) (React 19)
- **Routing**: [TanStack Router](https://tanstack.com/router) (file-based routing)
- **Data Fetching**: [TanStack React Query](https://tanstack.com/query) with IndexedDB persistence
- **State Management**: [Zustand](https://zustand-demo.pmnd.rs/) for UI state
- **Styling**: [Tailwind CSS v4](https://tailwindcss.com/) with [Radix UI](https://radix-ui.com/) primitives
- **Authentication**: [Auth0](https://auth0.com/) with dev mode support
- **Testing**: [Vitest](https://vitest.dev/) + [React Testing Library](https://testing-library.com/react)

## Getting Started

### Prerequisites

- Node.js 20+
- npm or pnpm

### Installation

```bash
npm install
```

### Development

```bash
npm run dev
```

The app will be available at `http://localhost:5173`.

### Environment Variables

Create a `.env.local` file with:

```env
# API Configuration
VITE_API_BASE_URL=http://localhost:8000

# Auth0 Configuration (optional - uses dev mode if not set)
VITE_AUTH0_DOMAIN=your-auth0-domain
VITE_AUTH0_CLIENT_ID=your-client-id
VITE_AUTH0_AUDIENCE=your-audience

# Dev Mode: Set this to skip Auth0 and use a token directly
VITE_ACCESS_TOKEN=your-dev-token
```

## Available Scripts

| Script | Description |
|--------|-------------|
| `npm run dev` | Start development server |
| `npm run build` | Build for production |
| `npm run preview` | Preview production build |
| `npm run test` | Run tests |
| `npm run lint` | Run ESLint |
| `npm run lint:fix` | Fix ESLint issues |
| `npm run format` | Format code with Prettier |
| `npm run format:check` | Check code formatting |
| `npm run typecheck` | Run TypeScript type checking |

## Project Structure

```
src/
├── __tests__/          # Test setup and global test utilities
├── components/
│   ├── ui/             # Reusable UI components (buttons, dialogs, tables)
│   ├── icons/          # SVG icons and brand assets
│   └── mdx/            # MDX rendering components
├── config/             # App configuration (auth, navigation, theme)
├── features/           # Feature-specific modules
│   ├── api-keys/       # API key management
│   └── auth-providers/ # Auth provider configuration
├── hooks/              # Custom React hooks
├── lib/
│   ├── api/            # API client modules
│   └── *.ts            # Utility functions
├── routes/             # File-based route definitions
├── stores/             # Zustand state stores
└── styles.css          # Global styles and Tailwind config
```

## Key Patterns

### File-Based Routing

Routes are defined in `src/routes/`. TanStack Router automatically generates the route tree.

```
src/routes/
├── __root.tsx          # Root layout
├── index.tsx           # Home page (/)
├── api-keys.tsx        # API keys page (/api-keys)
└── auth-providers.tsx  # Auth providers (/auth-providers)
```

### Feature Modules

Each feature is self-contained with its own components, utilities, and tests:

```
features/api-keys/
├── components/         # Feature-specific components
├── utils/              # Helper functions
├── __tests__/          # Feature tests
└── index.ts            # Public exports
```

### API Client

The API client is organized by feature in `lib/api/`:

```typescript
import { fetchApiKeys, createApiKey } from "@/lib/api";
// or import directly from feature module
import { fetchApiKeys } from "@/lib/api/api-keys";
```

### UI Components

Reusable UI components are in `components/ui/`:

```typescript
import { Button } from "@/components/ui/button";
import { LoadingState } from "@/components/ui/loading-state";
import { ErrorState } from "@/components/ui/error-state";
```

## Testing

Tests are located alongside the code they test in `__tests__/` directories:

```bash
# Run all tests
npm run test

# Run tests in watch mode
npx vitest

# Run tests with coverage
npx vitest --coverage
```

## Contributing

1. Follow the existing code patterns and directory structure
2. Add tests for new utilities and complex logic
3. Run `npm run lint` and `npm run typecheck` before committing
4. Use conventional commit messages

## Learn More

- [TanStack Documentation](https://tanstack.com)
- [Tailwind CSS Documentation](https://tailwindcss.com/docs)
- [Radix UI Documentation](https://www.radix-ui.com/docs/primitives)
