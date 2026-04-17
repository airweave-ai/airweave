import * as React from 'react';
import { IconCheck, IconCopy } from '@tabler/icons-react';
import { Button } from '@/shared/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/ui/select';
import { cn } from '@/shared/tailwind/cn';

export interface CodeSnippetAsideLanguageOption<
  TValue extends string = string,
> {
  label: string;
  value: TValue;
}

export const codeSnippetLanguageOptions = [
  { label: 'Python', value: 'python' },
  { label: 'Node.js', value: 'node' },
] as const;

export function CodeSnippetAside({
  className,
  ...props
}: React.ComponentProps<'div'>) {
  return (
    <div
      className={cn(
        'flex min-h-0 flex-col text-card-foreground lg:h-full',
        className,
      )}
      {...props}
    />
  );
}

export function CodeSnippetAsideContent({
  className,
  ...props
}: React.ComponentProps<'div'>) {
  return (
    <div
      className={cn(
        'px-4 py-4 lg:min-h-0 lg:flex-1 lg:overflow-y-auto',
        className,
      )}
      {...props}
    />
  );
}

export function CodeSnippetAsideSection({
  actions,
  children,
  className,
  label,
  ...props
}: React.ComponentProps<'section'> & {
  actions?: React.ReactNode;
  label: string;
}) {
  return (
    <section
      className={cn(
        'space-y-3 border-b border-border py-4 first:pt-0 last:border-b-0 last:pb-0',
        className,
      )}
      {...props}
    >
      <div className="flex items-center justify-between gap-3">
        <p className="font-mono text-xs font-medium text-muted-foreground uppercase">
          {label}
        </p>

        {actions ? (
          <div className="flex items-center gap-2">{actions}</div>
        ) : null}
      </div>

      {children}
    </section>
  );
}

export function CodeSnippetAsideLanguageSelect<TValue extends string>({
  onValueChange,
  options,
  value,
}: {
  onValueChange: (value: TValue) => void;
  options: ReadonlyArray<CodeSnippetAsideLanguageOption<TValue>>;
  value: TValue;
}) {
  return (
    <Select
      value={value}
      onValueChange={(nextValue) => onValueChange(nextValue as TValue)}
    >
      <SelectTrigger
        aria-label="Select code language"
        size="sm"
        className="!h-5.5 dark:bg-transparent"
      >
        <SelectValue />
      </SelectTrigger>

      <SelectContent position="popper">
        {options.map((option) => (
          <SelectItem key={option.value} value={option.value}>
            {option.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

export function CopyCodeSnippetButton({
  copied,
  onClick,
}: {
  copied: boolean;
  onClick: () => void;
}) {
  return (
    <Button type="button" variant="ghost" size="icon-sm" onClick={onClick}>
      {copied ? (
        <IconCheck className="size-3.5" />
      ) : (
        <IconCopy className="size-3.5" />
      )}
      <span className="sr-only">Copy request snippet</span>
    </Button>
  );
}
