export type Store = {
  get(key: string): Promise<string | null>;
  put(key: string, value: string, ttlSeconds?: number): Promise<void>;
};

export type Settings = {
  enabled: boolean;
  limit: number;
  periodDays: number;
  minScore: number;
};

export const defaultSettings: Settings = {
  enabled: true,
  limit: 5,
  periodDays: 14,
  minScore: 78,
};

export async function readSettings(store: Store, fallback: Settings = defaultSettings): Promise<Settings> {
  const raw = await store.get("settings");
  if (!raw) return fallback;
  try {
    const parsed = JSON.parse(raw) as Partial<Settings>;
    return {
      enabled: parsed.enabled ?? fallback.enabled,
      limit: parsed.limit ?? fallback.limit,
      periodDays: parsed.periodDays ?? fallback.periodDays,
      minScore: parsed.minScore ?? fallback.minScore,
    };
  } catch {
    return fallback;
  }
}

export async function writeSettings(store: Store, settings: Settings): Promise<void> {
  await store.put("settings", JSON.stringify(settings));
}

export function memoryStore(): Store {
  const values = new Map<string, string>();
  return {
    async get(key) {
      return values.get(key) ?? null;
    },
    async put(key, value) {
      values.set(key, value);
    },
  };
}
