export type AuthenticationMethod =
  | "direct"
  | "oauth_browser"
  | "oauth_token"
  | "oauth_byoc"
  | "auth_provider";

// Available source/integration from /connect/sources
export interface Source {
  name: string;
  short_name: string;
  auth_method: AuthenticationMethod;
}

// Config field definition for dynamic forms
export interface ConfigField {
  name: string;
  title: string;
  description?: string;
  type: "string" | "number" | "boolean" | "array";
  required: boolean;
  items_type?: string;
  is_secret?: boolean;
}

// Fields wrapper (matches backend response structure)
export interface Fields {
  fields: ConfigField[];
}

// Source details from GET /connect/sources/{short_name}
export interface SourceDetails {
  name: string;
  short_name: string;
  description?: string;
  auth_methods: AuthenticationMethod[];
  oauth_type?:
    | "oauth1"
    | "access_only"
    | "with_refresh"
    | "with_rotating_refresh";
  requires_byoc: boolean;
  auth_fields?: Fields;
  config_fields?: Fields;
}
