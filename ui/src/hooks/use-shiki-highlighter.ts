'use client'

import { useTheme } from 'next-themes'
import * as React from 'react'
import { createHighlighter, type Highlighter } from 'shiki'

export interface UseShikiHighlighterOptions {
  code: string
  language: string
  langs?: string[]
}

export interface UseShikiHighlighterResult {
  highlightedCode: string
  isLoading: boolean
}

export function useShikiHighlighter({
  code,
  language,
  langs = [],
}: UseShikiHighlighterOptions): UseShikiHighlighterResult {
  const { theme, resolvedTheme } = useTheme()
  const [highlightedCode, setHighlightedCode] = React.useState<string>('')
  const [isLoading, setIsLoading] = React.useState(true)
  const highlighterRef = React.useRef<Highlighter | null>(null)

  React.useEffect(() => {
    let isMounted = true

    const initHighlighter = async () => {
      try {
        if (!highlighterRef.current) {
          highlighterRef.current = await createHighlighter({
            themes: ['github-dark', 'github-light'],
            langs: [language, 'json', 'bash', 'shell', ...langs],
          })
        }

        if (!isMounted) return

        const currentTheme =
          resolvedTheme === 'dark' || theme === 'dark'
            ? 'github-dark'
            : 'github-light'

        const html = highlighterRef.current.codeToHtml(code, {
          lang: language,
          theme: currentTheme,
        })

        if (isMounted) {
          setHighlightedCode(html)
          setIsLoading(false)
        }
      } catch (error) {
        console.error('Error highlighting code:', error)
        if (isMounted) {
          setHighlightedCode(code)
          setIsLoading(false)
        }
      }
    }

    initHighlighter()

    return () => {
      isMounted = false
    }
  }, [code, language, langs, theme, resolvedTheme])

  return { highlightedCode, isLoading }
}
