import { getAppIconUrl } from '@/shared/icons/get-app-icon-url';
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
        {IDE_READY_AGENT_SHORT_NAMES.map((shortName, index) => {
          const iconUrl = getAppIconUrl(shortName, 'color');

          if (!iconUrl) {
            return null;
          }

          return (
            <span
              key={shortName}
              className="flex size-6 items-center justify-center rounded-full bg-background"
              style={{ zIndex: IDE_READY_AGENT_SHORT_NAMES.length - index }}
            >
              <img
                alt=""
                aria-hidden="true"
                className="size-5 object-contain"
                src={iconUrl}
              />
            </span>
          );
        })}
      </span>
    </Button>
  );
}
