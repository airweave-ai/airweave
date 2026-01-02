import { FileText, Inbox, Search } from "lucide-react";
import { Button } from "../components/ui/button";
import { EmptyState } from "../components/ui/empty-state";
import type { ComponentPreviewConfig } from "./types";

export const emptyStatePreview: ComponentPreviewConfig = {
  variants: [
    {
      title: "Default",
      description: "An empty state with icon, title, and description",
      preview: (
        <EmptyState
          icon={<Inbox />}
          title="No messages"
          description="You don't have any messages yet. Start a conversation!"
        />
      ),
      code: `<EmptyState
  icon={<Inbox />}
  title="No messages"
  description="You don't have any messages yet. Start a conversation!"
/>`,
    },
    {
      title: "With Action",
      description: "Empty state with a call-to-action button",
      preview: (
        <EmptyState
          icon={<FileText />}
          title="No documents"
          description="Get started by creating your first document."
        >
          <Button>Create Document</Button>
        </EmptyState>
      ),
      code: `<EmptyState
  icon={<FileText />}
  title="No documents"
  description="Get started by creating your first document."
>
  <Button>Create Document</Button>
</EmptyState>`,
    },
    {
      title: "Search Results",
      description: "Empty state for no search results",
      preview: (
        <EmptyState
          icon={<Search />}
          title="No results found"
          description="Try adjusting your search or filter to find what you're looking for."
        >
          <Button variant="outline">Clear filters</Button>
        </EmptyState>
      ),
      code: `<EmptyState
  icon={<Search />}
  title="No results found"
  description="Try adjusting your search or filter to find what you're looking for."
>
  <Button variant="outline">Clear filters</Button>
</EmptyState>`,
    },
  ],
};

