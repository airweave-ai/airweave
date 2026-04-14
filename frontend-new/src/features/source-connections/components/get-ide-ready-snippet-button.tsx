import { SourceIcon } from '@/shared/components/source-icon';
import { Button } from '@/shared/ui/button';

const IDE_READY_AGENT_SHORT_NAMES = [
  'cursor',
  'claude-code',
  'chatgpt',
] as const;

export function GetIdeReadySnippetButton() {
  return (
    <Button
      type="button"
      variant="outline"
      size="lg"
      className="w-full gap-2 font-mono text-sm text-muted-foreground uppercase dark:bg-transparent"
    >
      <span>Get IDE-ready snippet</span>
      <span className="flex items-center -space-x-2">
        {IDE_READY_AGENT_SHORT_NAMES.map((shortName, index) => (
          <SourceIcon
            key={shortName}
            aria-hidden="true"
            className="size-6 rounded-full bg-background p-0.5"
            name={shortName}
            shortName={shortName}
            style={{ zIndex: IDE_READY_AGENT_SHORT_NAMES.length - index }}
            variant="color"
          />
        ))}
      </span>
    </Button>
  );
}
