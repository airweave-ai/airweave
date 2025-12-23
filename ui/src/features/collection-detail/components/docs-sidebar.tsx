import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  IconBrandOpenai,
  IconCopy,
  IconExternalLink,
  IconMarkdown,
  IconMenu2,
  IconThumbDown,
  IconThumbUp,
} from '@tabler/icons-react'

export function DocsSidebar() {
  return (
    <div className="flex flex-col h-full">
      <header className="border-b shrink-0 px-4 py-2 flex justify-between items-center gap-3">
        <div className="shrink-0 flex gap-2">
          <Button variant="outline" size="icon">
            <IconMenu2 />
            <span className="sr-only">Menu</span>
          </Button>
        </div>
        <h2 className="font-medium grow truncate">Collection</h2>
        <div className="shrink-0 flex gap-2">
          <DropdownMenu>
            <DropdownMenuTrigger
              render={
                <Button variant="outline" size="icon">
                  <IconCopy />
                  <span className="sr-only">Copy</span>
                </Button>
              }
            />
            <DropdownMenuContent className="w-48">
              <DropdownMenuItem>
                <IconMarkdown className="opacity-60" />
                Copy as markdown
              </DropdownMenuItem>
              <DropdownMenuItem>
                <IconBrandOpenai className="opacity-60" />
                Open in ChatGPT
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
          <Button variant="outline" size="icon">
            <IconExternalLink />
            <span className="sr-only">Links</span>
          </Button>
        </div>
      </header>
      <article className="p-4 space-y-4 grow opacity-80">
        <p>
          A <strong className="font-medium">Collection</strong> is a searchable
          knowledge base made up of synced data from one or more source
          connections. When you search a collection, queries run across all
          entities from all its connected sources.
        </p>
        <p>
          <strong className="font-medium">Key features:</strong>
        </p>
        <p>
          <ul className="list-disc list-inside space-y-1">
            <li>Unified search interface across multiple sources</li>
            <li>Vector embeddings for semantic search</li>
            <li>Real-time data synchronization</li>
            <li>Configurable search parameters and filters</li>
          </ul>
        </p>
        <p className="border-t border-muted pt-4">
          <strong className="font-medium">Search settings explained:</strong>
        </p>
        <p>
          <ul className="list-disc list-inside space-y-4">
            <li>
              <strong className="font-medium">Search Method</strong>: pick how
              results are ranked. Hybrid blends semantic vectors with keywords,
              Neural is semantic-only, and Keyword sticks to exact text matches.
            </li>
            <li>
              <strong className="font-medium">Query Expansion</strong>: rewrites
              or augments the query with synonyms/related terms to widen recall.
              Turn off for precise lookups.
            </li>
            <li>
              <strong className="font-medium">Query Interpretation</strong>:
              lets the system infer intent (filters, entities, date ranges) from
              natural language before searching. Disable to run the literal
              text.
            </li>
            <li>
              <strong className="font-medium">AI Reranking</strong>: uses an LLM
              to reorder the top candidates from search so the most relevant
              answers appear first.
            </li>
            <li>
              <strong className="font-medium">Recency Bias</strong>: increases
              the weight of newer items. Higher values favor fresh content;
              lower values prefer overall relevance.
            </li>
            <li>
              <strong className="font-medium">Metadata Filtering</strong>: JSON
              filters applied before search (e.g.,{' '}
              {`{"author":"alice","type":"doc"}`}) to scope results to specific
              attributes.
            </li>
          </ul>
        </p>
      </article>
      <footer className="border-t shrink-0 px-4 py-2 flex justify-between items-center">
        <h2 className="text-muted-foreground grow truncate">
          Were these docs helpful?
        </h2>
        <div className="shrink-0 flex gap-2">
          <Button variant="outline" size="sm">
            <IconThumbUp />
            <span>Yes</span>
          </Button>
          <Button variant="outline" size="sm">
            <IconThumbDown />
            <span>No</span>
          </Button>
        </div>
      </footer>
    </div>
  )
}
