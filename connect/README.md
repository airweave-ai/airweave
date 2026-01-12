# Airweave Connect

Airweave Connect is a frontend application for connecting data sources to Airweave, making any app searchable for your agent.

## Getting Started

To run this application:

```bash
npm install
npm run dev
```

The app will be available at http://localhost:3000

## Building For Production

To build this application for production:

```bash
npm run build
```

## Testing

This project uses [Vitest](https://vitest.dev/) for testing. You can run the tests with:

```bash
npm run test
```

## Tech Stack

- **Framework**: [TanStack Start](https://tanstack.com/start) - Full-stack React framework
- **Routing**: [TanStack Router](https://tanstack.com/router) - Type-safe file-based routing
- **Styling**: [Tailwind CSS](https://tailwindcss.com/) - Utility-first CSS framework
- **Icons**: [Lucide React](https://lucide.dev/) - Beautiful & consistent icons

## Project Structure

```
connect/
├── public/           # Static assets
├── src/
│   ├── components/   # Reusable UI components
│   ├── data/         # Data files and constants
│   ├── routes/       # File-based routes
│   │   ├── __root.tsx    # Root layout
│   │   ├── index.tsx     # Home page
│   │   └── demo/         # Demo routes
│   ├── router.tsx    # Router configuration
│   └── styles.css    # Global styles
├── package.json
├── tsconfig.json
└── vite.config.ts
```

## Adding Routes

To add a new route, create a new file in the `./src/routes` directory. TanStack Router will automatically generate the route.

Example: Creating `src/routes/integrations.tsx` will create the `/integrations` route.

## Learn More

- [Airweave Documentation](https://docs.airweave.io)
- [TanStack Start Documentation](https://tanstack.com/start)
- [TanStack Router Documentation](https://tanstack.com/router)
