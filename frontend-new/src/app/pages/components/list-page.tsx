import { Search } from 'lucide-react';
import type { ReactNode } from 'react';
import { cn } from '@/shared/tailwind/cn';
import {
  InputGroup,
  InputGroupAddon,
  InputGroupInput,
} from '@/shared/ui/input-group';
import { Spinner } from '@/shared/ui/spinner';

export function ListPage({
  className,
  ...props
}: React.ComponentProps<'section'>) {
  return (
    <section
      className={cn('flex min-h-full flex-1 flex-col gap-5 px-16 py-4', className)}
      {...props}
    />
  );
}

type ListPageHeaderProps = {
  title: ReactNode;
  badge?: ReactNode;
  actions?: ReactNode;
  className?: string;
};

export function ListPageHeader({
  title,
  badge,
  actions,
  className,
}: ListPageHeaderProps) {
  return (
    <div
      className={cn(
        'flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between',
        className,
      )}
    >
      <div className="flex items-center gap-1">
        <h1 className="font-heading text-lg font-semibold text-foreground">
          {title}
        </h1>
        {badge}
      </div>

      {actions ? (
        <div className="flex flex-wrap items-center gap-2">{actions}</div>
      ) : null}
    </div>
  );
}

type ListPageSearchProps = {
  value?: string;
  onChange: (value: string | undefined) => void;
  placeholder: string;
  isFetching?: boolean;
  loadingLabel?: string;
  className?: string;
};

export function ListPageSearch({
  value,
  onChange,
  placeholder,
  isFetching,
  loadingLabel,
  className,
}: ListPageSearchProps) {
  const showLoadingState = loadingLabel !== undefined || isFetching !== undefined;

  return (
    <InputGroup className={cn('w-full', className)}>
      <InputGroupAddon align="inline-start">
        <Search className="size-4" />
      </InputGroupAddon>

      <InputGroupInput
        value={value ?? ''}
        onChange={(event) => onChange(event.target.value || undefined)}
        placeholder={placeholder}
      />

      {showLoadingState ? (
        <InputGroupAddon
          align="inline-end"
          aria-hidden={!isFetching}
          className="w-8 justify-center"
        >
          <Spinner
            className={cn(
              'size-4 transition-opacity duration-150',
              isFetching ? 'opacity-100 delay-150' : 'opacity-0 delay-0',
            )}
          />
          <span className="sr-only">{loadingLabel ?? 'Loading results'}</span>
        </InputGroupAddon>
      ) : null}
    </InputGroup>
  );
}

export function ListPageState({
  className,
  ...props
}: React.ComponentProps<'div'>) {
  return (
    <div
      className={cn('flex min-h-0 flex-1 items-center justify-center', className)}
      {...props}
    />
  );
}
