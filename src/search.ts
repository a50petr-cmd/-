import { isAddedRole, isRecent, rankVacancies, titleScore } from "./match.ts";
import { enrichVacancy, searchHabr, searchHh, searchSuperjob, searchTrudvsem, searchZarplata, type FetchLike } from "./sources.ts";
import type { Store } from "./store.ts";
import { normalizeKey } from "./text.ts";
import type { ScoredVacancy, SourceId, SourceReport, Vacancy } from "./types.ts";

const SOURCE_ORDER: Record<SourceId, number> = {
  hh: 0,
  zarplata: 1,
  superjob: 2,
  habr: 3,
  trudvsem: 4,
};

export function seenKey(dedupeKey: string): string {
  return `seen:${dedupeKey}`;
}

export function skipKey(dedupeKey: string): string {
  return `skip:${dedupeKey}`;
}

export function dedupeVacancies(vacancies: Vacancy[]): Vacancy[] {
  const byId = new Map<string, Vacancy>();
  const byFuzzy = new Map<string, string>();
  for (const vacancy of vacancies) {
    const current = byId.get(vacancy.dedupeKey);
    if (!current || SOURCE_ORDER[vacancy.source] < SOURCE_ORDER[current.source]) {
      byId.set(vacancy.dedupeKey, vacancy);
    }
    if (!vacancy.company) continue;
    const fuzzy = `${normalizeKey(vacancy.title)}|${normalizeKey(vacancy.company)}`;
    const previousKey = byFuzzy.get(fuzzy);
    if (!previousKey) {
      byFuzzy.set(fuzzy, vacancy.dedupeKey);
      continue;
    }
    const previous = byId.get(previousKey);
    const incoming = byId.get(vacancy.dedupeKey) ?? vacancy;
    if (previous && SOURCE_ORDER[incoming.source] < SOURCE_ORDER[previous.source]) {
      byId.delete(previousKey);
      byId.set(incoming.dedupeKey, incoming);
      byFuzzy.set(fuzzy, incoming.dedupeKey);
    } else if (previous && previousKey !== vacancy.dedupeKey) {
      byId.delete(vacancy.dedupeKey);
    }
  }
  return [...byId.values()];
}

async function mapPool<T, R>(items: T[], limit: number, fn: (item: T) => Promise<R>): Promise<R[]> {
  const output: R[] = new Array(items.length);
  let cursor = 0;
  async function worker(): Promise<void> {
    while (cursor < items.length) {
      const index = cursor;
      cursor += 1;
      output[index] = await fn(items[index]);
    }
  }
  await Promise.all(Array.from({ length: Math.min(limit, items.length) }, () => worker()));
  return output;
}

export async function findVacancies(options: {
  fetch: FetchLike;
  store?: Store;
  now: Date;
  periodDays: number;
  enrichLimit: number;
  superjobKey?: string;
}): Promise<{ reports: SourceReport[]; vacancies: Vacancy[] }> {
  const batches = await Promise.all([
    searchHh(options.fetch),
    searchZarplata(options.fetch),
    searchHabr(options.fetch),
    searchTrudvsem(options.fetch),
    searchSuperjob(options.fetch, options.superjobKey),
  ]);
  const reports = batches.map((batch) => batch.report);
  const now = options.now.getTime();
  let vacancies = dedupeVacancies(batches.flatMap((batch) => batch.vacancies))
    .filter((vacancy) => titleScore(vacancy.title) >= 26)
    .filter((vacancy) => isRecent(vacancy.publishedAt, now, options.periodDays))
    .sort((a, b) => titleScore(b.title) - titleScore(a.title) || Date.parse(b.publishedAt) - Date.parse(a.publishedAt));

  if (options.store) {
    const unseen: Vacancy[] = [];
    for (const vacancy of vacancies) {
      const [seen, skipped] = await Promise.all([
        options.store.get(seenKey(vacancy.dedupeKey)),
        options.store.get(skipKey(vacancy.dedupeKey)),
      ]);
      if (!seen && !skipped) unseen.push(vacancy);
    }
    vacancies = unseen;
  }

  const enriched = await mapPool(pickForEnrich(vacancies, options.enrichLimit), 3, (vacancy) => enrichVacancy(options.fetch, vacancy));
  return { reports, vacancies: enriched };
}

export function pickForEnrich(vacancies: Vacancy[], limit: number): Vacancy[] {
  const added = vacancies.filter((vacancy) => isAddedRole(vacancy.title));
  const primary = vacancies.filter((vacancy) => !isAddedRole(vacancy.title));
  const addedTake = Math.min(added.length, Math.ceil(limit / 2));
  const primaryTake = Math.min(primary.length, limit - addedTake);
  const extraAdded = Math.min(added.length - addedTake, limit - addedTake - primaryTake);
  return [...primary.slice(0, primaryTake), ...added.slice(0, addedTake + extraAdded)];
}

export function selectMatches(
  vacancies: Vacancy[],
  options: { now: number; periodDays: number; minScore: number; limit: number },
): ScoredVacancy[] {
  return rankVacancies(vacancies, options);
}
