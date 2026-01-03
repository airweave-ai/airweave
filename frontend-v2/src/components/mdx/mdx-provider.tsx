import { MDXProvider } from "@mdx-js/react";
import type { ReactNode } from "react";

import { mdxComponents } from "./mdx-components";

interface MdxProviderProps {
  children: ReactNode;
}

export function MdxProvider({ children }: MdxProviderProps) {
  return <MDXProvider components={mdxComponents}>{children}</MDXProvider>;
}

export default MdxProvider;
