import '@tanstack/react-router';
import type { BreadcrumbValue } from './breadcrumbs';

declare module '@tanstack/react-router' {
  interface StaticDataRouteOption {
    breadcrumb?: BreadcrumbValue;
  }
}
