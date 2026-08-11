export type ChatSummary = {
  id: string;
  name: string;
  is_archived: boolean;
  created_at: string;
  updated_at: string;
  message_count: number;
};

export type Citation = {
  scripture: string;
  page: number | string;
  file_name: string;
  score: number;
  excerpt: string;
  source_text?: string;
  verse_text?: string;
  sanskrit_text?: string;
  translation?: string;
};

export type Message = {
  id: number;
  role: "user" | "assistant";
  content: string;
  mode: string;
  sources: Citation[];
  created_at: string;
};

export type GenerationRun = {
  id: string;
  chat: string;
  state: "queued" | "running" | "completed" | "failed" | "cancelled";
  model_profile: string;
  last_event_id: string;
  final_text: string;
  final_sources: Citation[];
  error_code: string;
  queued_at: string;
  started_at: string | null;
  finished_at: string | null;
};

export type ModelConnection = {
  id: string;
  name: string;
  dialect: "openai_compatible" | "ollama_compatible" | "builtin_ollama";
  endpoint_url: string;
  status: string;
  sanitized_detail: string;
  remote_data_consent_at: string | null;
  last_checked_at: string | null;
  created_at: string;
  updated_at: string;
};

export type ModelProfile = {
  id: string;
  name: string;
  model_id: string;
  connection: string | null;
  connection_status: string;
  connection_dialect: string;
  is_enabled: boolean;
  is_admin_default: boolean;
  context_window: number;
  max_output_tokens: number;
  temperature: number;
};

export type UserModelPreference = {
  primary_profile: string | null;
  primary_profile_detail: ModelProfile | null;
  ordered_fallback_profile_ids: string[];
  updated_at: string;
};

export type Page<T> = {
  next: string | null;
  previous: string | null;
  results: T[];
};

export type UserProfile = {
  id: number;
  email: string;
  spiritual_name: string;
  preferred_theme: "system" | "light" | "dark";
  created_at: string;
};

export type Scripture = {
  id: number;
  name: string;
  folder_path: string;
  is_indexed: boolean;
  total_volumes: number;
  total_pages: number;
  last_indexed_at: string | null;
  current_indexing_job: {
    status: "PENDING" | "RUNNING";
    progress: number;
    chunks_indexed: number;
    volumes_processed: number;
    source_pages: number;
  } | null;
  latest_indexing_failure: {
    failure_code: string;
    finished_at: string | null;
  } | null;
};
