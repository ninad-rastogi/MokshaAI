export type ChatSummary = {
  id: string;
  name: string;
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

export type Page<T> = {
  next: string | null;
  previous: string | null;
  results: T[];
};

export type UserProfile = {
  id: number;
  email: string;
  spiritual_name: string;
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
};
