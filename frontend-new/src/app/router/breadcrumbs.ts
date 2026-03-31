export interface BreadcrumbResolverMatch {
  id: string;
  pathname: string;
  params: Record<string, string>;
  loaderData: unknown;
}

export type BreadcrumbValue =
  | string
  | string[]
  | null
  | undefined
  | ((match: BreadcrumbResolverMatch) => string | string[] | null | undefined);
