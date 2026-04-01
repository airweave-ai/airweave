export interface BreadcrumbResolverMatch {
  id: string;
  pathname: string;
  params: Record<string, string>;
  loaderData: unknown;
}

export type BreadcrumbValue =
  | string
  | Array<string>
  | null
  | undefined
  | ((
      match: BreadcrumbResolverMatch,
    ) => string | Array<string> | null | undefined);
