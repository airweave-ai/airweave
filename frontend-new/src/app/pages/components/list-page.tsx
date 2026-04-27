import { Search } from 'lucide-react';
import { PageHeader, PageLayout } from './page-layout';
import type { PageHeaderProps } from './page-layout';
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
  return <PageLayout className={cn('gap-5', className)} {...props} />;
}

export function ListPageHeader({ ...props }: PageHeaderProps) {
  return <PageHeader {...props} />;
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
  const showLoadingState =
    loadingLabel !== undefined || isFetching !== undefined;

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
      className={cn(
        'flex min-h-0 flex-1 items-center justify-center',
        className,
      )}
      {...props}
    />
  );
}
