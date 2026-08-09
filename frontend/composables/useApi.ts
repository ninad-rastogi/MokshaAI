import { z } from "zod";
import type {
  ChatSummary,
  GenerationRun,
  Message,
  ModelConnection,
  ModelProfile,
  Page,
  Scripture,
  UserModelPreference,
  UserProfile,
} from "~/types/api";

const pageSchema = <T extends z.ZodTypeAny>(item: T) =>
  z.object({
    next: z.string().nullable(),
    previous: z.string().nullable(),
    results: z.array(item),
  });

const chatSchema = z.object({
  id: z.string(),
  name: z.string(),
  is_archived: z.boolean(),
  created_at: z.string(),
  updated_at: z.string(),
  message_count: z.number(),
});

const citationSchema = z.object({
  scripture: z.string(),
  page: z.union([z.number(), z.string()]),
  file_name: z.string(),
  score: z.number(),
  excerpt: z.string(),
  source_text: z.string().optional(),
  verse_text: z.string().optional(),
  sanskrit_text: z.string().optional(),
  translation: z.string().optional(),
});

const messageSchema = z.object({
  id: z.number(),
  role: z.enum(["user", "assistant"]),
  content: z.string(),
  mode: z.string(),
  sources: z.array(citationSchema),
  created_at: z.string(),
});

const runSchema = z.object({
  id: z.string(),
  chat: z.string(),
  state: z.enum(["queued", "running", "completed", "failed", "cancelled"]),
  model_profile: z.string(),
  last_event_id: z.string(),
  final_text: z.string(),
  final_sources: z.array(citationSchema),
  error_code: z.string(),
  queued_at: z.string(),
  started_at: z.string().nullable(),
  finished_at: z.string().nullable(),
});

const modelProfileSchema = z.object({
  id: z.string(),
  name: z.string(),
  model_id: z.string(),
  connection: z.string().nullable(),
  connection_status: z.string(),
  connection_dialect: z.string(),
  is_enabled: z.boolean(),
  is_admin_default: z.boolean(),
  context_window: z.number(),
  max_output_tokens: z.number(),
  temperature: z.number(),
});

const modelConnectionSchema = z.object({
  id: z.string(),
  name: z.string(),
  dialect: z.enum(["openai_compatible", "ollama_compatible", "builtin_ollama"]),
  endpoint_url: z.string(),
  status: z.string(),
  sanitized_detail: z.string(),
  remote_data_consent_at: z.string().nullable(),
  last_checked_at: z.string().nullable(),
  created_at: z.string(),
  updated_at: z.string(),
});

const modelConnectionProbeSchema = z.object({
  status: z.string(),
  detail: z.string(),
  models: z.array(z.string()),
});

const userModelPreferenceSchema = z.object({
  primary_profile: z.string().nullable(),
  primary_profile_detail: modelProfileSchema.nullable(),
  ordered_fallback_profile_ids: z.array(z.string()),
  updated_at: z.string(),
});

const userSchema = z.object({
  id: z.number(),
  email: z.string(),
  spiritual_name: z.string(),
  preferred_theme: z.enum(["system", "light", "dark"]),
  created_at: z.string(),
});

const scriptureSchema = z.object({
  id: z.number(),
  name: z.string(),
  folder_path: z.string(),
  is_indexed: z.boolean(),
  total_volumes: z.number(),
  total_pages: z.number(),
  last_indexed_at: z.string().nullable(),
  current_indexing_job: z
    .object({
      status: z.enum(["PENDING", "RUNNING"]),
      progress: z.number().int().min(0).max(100),
      chunks_indexed: z.number().int().nonnegative(),
      volumes_processed: z.number().int().nonnegative(),
    })
    .nullable(),
  latest_indexing_failure: z
    .object({
      failure_code: z.string(),
      finished_at: z.string().nullable(),
    })
    .nullable(),
});

const readinessSchema = z.object({
  status: z.enum(["ready", "unavailable"]),
  database: z.boolean(),
  redis: z.boolean(),
  ollama: z.boolean(),
  embedding: z.boolean(),
  disk: z.boolean(),
});

export class ApiRequestError extends Error {
  constructor(
    readonly status: number,
    readonly payload: unknown,
  ) {
    super(`request_failed:${status}`);
  }
}

async function responsePayload(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) return null;
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return text;
  }
}

export function useApi() {
  const config = useRuntimeConfig();
  const base = config.public.apiBase;
  const csrfToken = useState<string>("csrf-token", () => "");

  async function ensureCsrf() {
    if (csrfToken.value) return csrfToken.value;
    const response = await fetch(`${base}/auth/csrf/`, {
      credentials: "include",
    });
    if (!response.ok) throw new Error("csrf_failed");
    const data = z
      .object({ csrfToken: z.string() })
      .parse(await response.json());
    csrfToken.value = data.csrfToken;
    return csrfToken.value;
  }

  async function request<T>(
    path: string,
    schema: z.ZodType<T>,
    options: RequestInit = {},
  ): Promise<T> {
    const method = (options.method || "GET").toUpperCase();
    const token = method === "GET" ? "" : await ensureCsrf();
    const response = await fetch(`${base}${path}`, {
      ...options,
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { "X-CSRFToken": token } : {}),
        ...(options.headers || {}),
      },
    });
    if (!response.ok) {
      throw new ApiRequestError(
        response.status,
        await responsePayload(response),
      );
    }
    return schema.parse(await response.json());
  }

  async function readiness() {
    const response = await fetch(`${base}/auth/ready/`, {
      credentials: "include",
    });
    const payload = await responsePayload(response);
    return readinessSchema.parse(payload);
  }

  return {
    me: () => request<UserProfile>("/auth/me/", userSchema),
    readiness,
    updateMe: (data: Partial<Pick<UserProfile, "preferred_theme">>) =>
      request<UserProfile>("/auth/me/", userSchema, {
        method: "PUT",
        body: JSON.stringify(data),
      }),
    register: async (email: string, password: string) => {
      const user = await request<UserProfile>("/auth/register/", userSchema, {
        method: "POST",
        body: JSON.stringify({ email, password, password_confirm: password }),
      });
      csrfToken.value = "";
      await ensureCsrf();
      return user;
    },
    sessionLogin: async (email: string, password: string) => {
      const user = await request<UserProfile>(
        "/auth/session/login/",
        userSchema,
        {
          method: "POST",
          body: JSON.stringify({ email, password }),
        },
      );
      csrfToken.value = "";
      await ensureCsrf();
      return user;
    },
    sessionLogout: async () =>
      fetch(`${base}/auth/session/logout/`, {
        method: "POST",
        credentials: "include",
        headers: { "X-CSRFToken": await ensureCsrf() },
      }),
    chats: (archived = false) =>
      request<Page<ChatSummary>>(
        `/chats/?archived=${archived ? "true" : "false"}`,
        pageSchema(chatSchema),
      ),
    createChat: () =>
      request<ChatSummary>("/chats/", chatSchema, { method: "POST" }),
    renameChat: (chatId: string, name: string) =>
      request<ChatSummary>(`/chats/${chatId}/rename/`, chatSchema, {
        method: "PATCH",
        body: JSON.stringify({ name }),
      }),
    deleteChat: async (chatId: string) => {
      const token = await ensureCsrf();
      const response = await fetch(`${base}/chats/${chatId}/`, {
        method: "DELETE",
        credentials: "include",
        headers: { "X-CSRFToken": token },
      });
      if (!response.ok) {
        throw new ApiRequestError(
          response.status,
          await responsePayload(response),
        );
      }
    },
    archiveChat: (chatId: string) =>
      request<ChatSummary>(`/chats/${chatId}/archive/`, chatSchema, {
        method: "POST",
      }),
    unarchiveChat: (chatId: string) =>
      request<ChatSummary>(`/chats/${chatId}/unarchive/`, chatSchema, {
        method: "POST",
      }),
    messages: (chatId: string) =>
      request<Page<Message>>(
        `/chats/${chatId}/messages/`,
        pageSchema(messageSchema),
      ),
    createRun: (
      chatId: string,
      message: string,
      modelProfile: string,
      idempotencyKey: string,
    ) =>
      request<GenerationRun>(`/chats/${chatId}/runs/`, runSchema, {
        method: "POST",
        headers: { "Idempotency-Key": idempotencyKey },
        body: JSON.stringify({ message, model_profile: modelProfile }),
      }),
    run: (runId: string) =>
      request<GenerationRun>(`/runs/${runId}/`, runSchema),
    cancelRun: (runId: string) =>
      request<GenerationRun>(`/runs/${runId}/cancel/`, runSchema, {
        method: "POST",
      }),
    modelProfiles: () =>
      request<Page<ModelProfile>>(
        "/models/profiles/",
        pageSchema(modelProfileSchema),
      ),
    modelPreference: () =>
      request<UserModelPreference>(
        "/models/preferences/me/",
        userModelPreferenceSchema,
      ),
    updateModelPreference: (
      primaryProfile: string,
      orderedFallbackProfileIds: string[] = [],
    ) =>
      request<UserModelPreference>(
        "/models/preferences/me/",
        userModelPreferenceSchema,
        {
          method: "PUT",
          body: JSON.stringify({
            primary_profile: primaryProfile || null,
            ordered_fallback_profile_ids: orderedFallbackProfileIds,
          }),
        },
      ),
    createModelConnection: (payload: {
      name: string;
      dialect: "openai_compatible" | "ollama_compatible";
      endpoint_url: string;
      model_id: string;
      api_key: string;
      remote_data_consent: boolean;
    }) =>
      request<ModelConnection>("/models/connections/", modelConnectionSchema, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    deleteModelConnection: async (connectionId: string) => {
      const token = await ensureCsrf();
      const response = await fetch(
        `${base}/models/connections/${connectionId}/`,
        {
          method: "DELETE",
          credentials: "include",
          headers: { "X-CSRFToken": token },
        },
      );
      if (!response.ok) {
        throw new ApiRequestError(
          response.status,
          await responsePayload(response),
        );
      }
    },
    probeModelConnection: (connectionId: string) =>
      request(
        `/models/connections/${connectionId}/probe/`,
        modelConnectionProbeSchema,
        { method: "POST" },
      ),
    scriptures: () =>
      request<Page<Scripture>>("/scriptures/", pageSchema(scriptureSchema)),
  };
}
