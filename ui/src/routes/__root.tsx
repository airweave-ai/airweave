import { HeadContent, Scripts, createRootRoute } from '@tanstack/react-router'

import { ThemeProvider } from 'next-themes'
import appCss from '../styles.css?url'

export const Route = createRootRoute({
  head: () => ({
    meta: [
      { charSet: 'utf-8' },
      { name: 'viewport', content: 'width=device-width, initial-scale=1' },
      { title: 'Airweave' },
    ],
    links: [{ rel: 'stylesheet', href: appCss }],
  }),

  shellComponent: RootDocument,
})

function RootDocument({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <HeadContent />
      </head>
      <body>
        <ThemeProvider defaultTheme="dark" attribute="class">
          {children}
          {/* <TanStackDevtools
          config={{
            position: 'bottom-right',
          }}
          plugins={[
            {
              name: 'Tanstack Router',
              render: <TanStackRouterDevtoolsPanel />,
            },
          ]}
        /> */}
          <div className="fixed bottom-0 -left-48 -right-64 top-0 -z-10 bg-zinc-950">
            <video
              src="https://framerusercontent.com/assets/RfUXPn10oWk94UsML4m6oY4.mp4"
              loop
              preload="auto"
              muted
              playsInline
              className="w-full h-full object-cover opacity-50"
              autoPlay
            />
            <div
              className="absolute bottom-0 left-0 right-0 top-0 w-full h-full object-cover bg-repeat bg-center opacity-[0.15]"
              style={{
                backgroundImage:
                  'url("https://framerusercontent.com/images/6mcf62RlDfRfU61Yg5vb2pefpi4.png?width=256&height=256")',
              }}
            ></div>
          </div>
        </ThemeProvider>
        <Scripts />
      </body>
    </html>
  )
}
