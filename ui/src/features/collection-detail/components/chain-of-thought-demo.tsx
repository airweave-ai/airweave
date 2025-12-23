import {
  ChainOfThought,
  ChainOfThoughtContent,
  ChainOfThoughtSearchResult,
  ChainOfThoughtSearchResults,
  ChainOfThoughtStep,
} from '@/components/ai-elements/chain-of-thought'
import {
  InlineCitation,
  InlineCitationCard,
  InlineCitationCardBody,
  InlineCitationCardTrigger,
  InlineCitationCarousel,
  InlineCitationCarouselHeader,
  InlineCitationCarouselIndex,
  InlineCitationCarouselNext,
  InlineCitationCarouselPrev,
  InlineCitationText,
} from '@/components/ai-elements/inline-citation'
import { Button } from '@/components/ui/button'
import {
  IconChevronRight,
  IconSearch,
  IconSortDescending,
  IconWriting,
  IconZoomPan,
} from '@tabler/icons-react'

export function ChainOfThoughtDemo() {
  return (
    <ChainOfThought defaultOpen>
      <div className="flex justify-end pt-62">
        <div className="bg-primary text-sm text-primary-foreground rounded-xl p-4">
          Who is the main character in the story?
        </div>
      </div>
      <ChainOfThoughtContent>
        <ChainOfThoughtStep
          icon={IconZoomPan}
          label="Query Expansion"
          status="complete"
        >
          <ChainOfThoughtSearchResults>
            {[
              'Identify the protagonist of the story.',
              'What is the lead character in this narrative?',
              'Name the primary figure in the plot.',
              'Show the main character details.',
            ].map((alt) => (
              <ChainOfThoughtSearchResult key={alt}>{alt}</ChainOfThoughtSearchResult>
            ))}
          </ChainOfThoughtSearchResults>
        </ChainOfThoughtStep>

        <ChainOfThoughtStep
          icon={IconSearch}
          label="Retrieval · hybrid (5 neural, 5 BM25 embeddings)"
          status="complete"
          className="relative"
        >
          <Button size="xs" variant="secondary" className="absolute top-0 right-0">
            Entities
            <IconChevronRight />
          </Button>
          <ChainOfThoughtSearchResults>
            {[
              'Embeddings dim: 3072',
              'Retrieved 1,000 candidate results',
            ].map((detail) => (
              <ChainOfThoughtSearchResult key={detail}>
                {detail}
              </ChainOfThoughtSearchResult>
            ))}
          </ChainOfThoughtSearchResults>
        </ChainOfThoughtStep>

        <ChainOfThoughtStep
          icon={IconSortDescending}
          label="AI reranking top 1,000 results"
          status="complete"
        >
          <ChainOfThoughtSearchResults>
            {[
              '#1: Result 668 (relevance: 0.09)',
              '#2: Result 120 (relevance: 0.09)',
              '#3: Result 500 (relevance: 0.08)',
              '#4: Result 987 (relevance: 0.08)',
              '#5: Result 539 (relevance: 0.07)',
            ].map((result) => (
              <ChainOfThoughtSearchResult key={result}>
                {result}
              </ChainOfThoughtSearchResult>
            ))}
          </ChainOfThoughtSearchResults>
        </ChainOfThoughtStep>

        <ChainOfThoughtStep
          icon={IconWriting}
          label="Answer generation"
          status="active"
        >
          <div className="bg-muted/50 rounded-xl p-4">
            The main character appearing throughout the excerpts is Carlo Badini,
            the co-founder and CEO of FirstQuadrant. He is referenced in multiple
            items (e.g., the contact list showing{' '}
            <InlineCitation>
              <InlineCitationText>"Carlo Badini"</InlineCitationText>
              <InlineCitationCard>
                <InlineCitationCardTrigger sources={['https://Linear.com']} />
                <InlineCitationCardBody>
                  <InlineCitationCarousel>
                    <InlineCitationCarouselHeader>
                      <InlineCitationCarouselPrev />
                      <InlineCitationCarouselNext />
                      <InlineCitationCarouselIndex />
                    </InlineCitationCarouselHeader>
                  </InlineCitationCarousel>
                </InlineCitationCardBody>
              </InlineCitationCard>
            </InlineCitation>{' '}
            and comments/notes that mention his actions and{' '}
            <InlineCitation>
              <InlineCitationText>messages</InlineCitationText>
              <InlineCitationCard>
                <InlineCitationCardTrigger sources={['https://Linear.com']} />
                <InlineCitationCardBody>
                  <InlineCitationCarousel>
                    <InlineCitationCarouselHeader>
                      <InlineCitationCarouselPrev />
                      <InlineCitationCarouselNext />
                      <InlineCitationCarouselIndex />
                    </InlineCitationCarouselHeader>
                  </InlineCitationCarousel>
                </InlineCitationCardBody>
              </InlineCitationCard>
            </InlineCitation>
            ).
          </div>
        </ChainOfThoughtStep>
      </ChainOfThoughtContent>
    </ChainOfThought>
  )
}
