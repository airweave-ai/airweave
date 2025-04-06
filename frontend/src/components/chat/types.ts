export interface ModelSettings {
  temperature?: number;
  max_tokens?: number;
  top_p?: number;
  frequency_penalty?: number;
  presence_penalty?: number;
  search_type?: string;
}

export interface SourceConnection {
  id: string;
  name: string;
  type: string;
  short_name: string;
  status: string;
}

export interface ChatMessage {
  id: string;
  chat_id: string;
  content: string;
  role: "user" | "assistant";
  created_at: string;
  attachments?: string[];
}

export interface Chat {
  id: string;
  name: string;
  sync_id: string;
  description?: string;
  model_name: string;
  model_settings: ModelSettings;
  messages: ChatMessage[];
  created_at: string;
  modified_at: string;
  source_connection?: SourceConnection;
}

export interface Connection {
  id: string;
  name: string;
  short_name: string;
  status: string;
  source?: Source;
  destination?: Destination;
}

export interface Sync {
  id: string;
  name: string;
  description?: string;
  status: string;
  source_connection_id: string;
  destination_connection_id?: string;
  source_connection?: Connection;
  destination_connection?: Connection;
}

export interface ChatInfo {
  id: string;
  name: string;
  description?: string;
  model_name: string;
  model_settings: ModelSettings;
  sync_id: string;
  sync?: Sync;
}

export interface ChatInfoSidebarProps {
  chatInfo: ChatInfo;
  onUpdateSettings: (settings: Partial<ModelSettings> | { model_name: string } | { model_settings: ModelSettings }) => Promise<void>;
  className?: string;
}

export interface Source {
  id: string;
  name: string;
  short_name: string;
  app_url?: string;
}

export interface Destination {
  id: string;
  name: string;
  short_name: string;
  app_url?: string;
}
