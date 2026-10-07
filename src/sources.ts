import { extractWorkFormat, htmlToText, parseJobPosting, parseRssItems, pickCompany, rssField, vacancyIdFromUrl } from "./text.ts";
import type { SourceId, SourceReport, Vacancy } from "./types.ts";

export const USER_AGENT = "AlekseevJobBot/1.0 (https://t.me/PetroAlekseev)";

export type FetchLike = typeof fetch;

export async function fetchText(fetchImpl: FetchLike, url: string, headers: Record<string, string> = {}): Promise<string> {
  const response = await fetchImpl(url, {
    headers: {
      "User-Agent": USER_AGENT,
      Accept: "*/*",
      "Accept-Language": "ru,en;q=0.8",
      ...headers,
    },
    redirect: "follow",
    signal: AbortSignal.timeout(20_000),
  });
  if (!response.ok) throw new Error(`${response.status} ${new URL(url).host}`);
  return response.text();
}

function salaryOrEmpty(value: string): string {
  const text = value.replace(/\s+/g, " ").trim();
  if (!text || /не указан/i.test(text)) return "";
  return text;
}

function boardVacancy(source: SourceId, host: string, item: { title: string; link: string; pubDate: string; description: string }): Vacancy {
  const url = item.link.startsWith("http") ? item.link : new URL(item.link, host).toString();
  const id = vacancyIdFromUrl(url);
  const region = rssField(item.description, "Регион");
  return {
    source,
    id,
    dedupeKey: `board:${id}`,
    title: item.title,
    company: rssField(item.description, "Вакансия компании"),
    url,
    city: region,
    region,
    salary: salaryOrEmpty(rssField(item.description, "Предполагаемый уровень месячного дохода")),
    publishedAt: item.pubDate,
    workFormat: "",
    employment: "",
    description: "",
  };
}

function rssUrl(origin: string, text: string, area: string, remote: boolean): string {
  const url = new URL("/search/vacancy/rss", origin);
  url.searchParams.set("text", text);
  url.searchParams.set("search_field", "name");
  url.searchParams.set("area", area);
  url.searchParams.set("search_period", "14");
  url.searchParams.set("order_by", "publication_time");
  url.searchParams.set("employment", "full");
  url.searchParams.set("experience", "moreThan6");
  if (remote) {
    url.searchParams.append("work_format", "REMOTE");
    url.searchParams.append("work_format", "HYBRID");
  }
  return url.toString();
}

async function readBoard(
  fetchImpl: FetchLike,
  source: SourceId,
  origin: string,
  queries: Array<{ text: string; area: string; remote: boolean }>,
): Promise<{ report: SourceReport; vacancies: Vacancy[] }> {
  const vacancies: Vacancy[] = [];
  const errors: string[] = [];
  for (const query of queries) {
    try {
      const xml = await fetchText(fetchImpl, rssUrl(origin, query.text, query.area, query.remote));
      for (const item of parseRssItems(xml)) vacancies.push(boardVacancy(source, origin, item));
    } catch (error) {
      errors.push(error instanceof Error ? error.message : String(error));
    }
  }
  return {
    report: {
      source: source === "hh" ? "hh.ru" : "Зарплата.ру",
      ok: errors.length < queries.length,
      count: vacancies.length,
      error: errors[0],
    },
    vacancies,
  };
}

export function hhQueries(): Array<{ text: string; area: string; remote: boolean }> {
  const main = ["операционный директор", "COO"];
  const extra = ["директор по операционной деятельности", "Head of Operations"];
  return [
    ...[...main, ...extra].map((text) => ({ text, area: "1", remote: false })),
    ...main.map((text) => ({ text, area: "2019", remote: false })),
    ...main.map((text) => ({ text, area: "113", remote: true })),
  ];
}

export function zarplataQueries(): Array<{ text: string; area: string; remote: boolean }> {
  const main = ["операционный директор", "COO"];
  return [
    ...main.map((text) => ({ text, area: "1", remote: false })),
    ...main.map((text) => ({ text, area: "113", remote: true })),
  ];
}

export async function searchHh(fetchImpl: FetchLike): Promise<{ report: SourceReport; vacancies: Vacancy[] }> {
  return readBoard(fetchImpl, "hh", "https://hh.ru", hhQueries());
}

export async function searchZarplata(fetchImpl: FetchLike): Promise<{ report: SourceReport; vacancies: Vacancy[] }> {
  return readBoard(fetchImpl, "zarplata", "https://zarplata.ru", zarplataQueries());
}

type TrudVacancy = {
  id?: string;
  region?: { name?: string };
  company?: { name?: string };
  salary?: string;
  "job-name"?: string;
  vac_url?: string;
  "creation-date"?: string;
  schedule?: string;
  duty?: string;
  requirements?: string;
  requirement?: { experience?: number };
};

export function mapTrudVacancy(raw: TrudVacancy): Vacancy | null {
  const title = raw["job-name"]?.trim() ?? "";
  const url = raw.vac_url?.trim() ?? "";
  if (!title || !url) return null;
  const duty = raw.duty?.trim() ?? "";
  const requirements = raw.requirements?.trim() ?? "";
  return {
    source: "trudvsem",
    id: raw.id ?? url,
    dedupeKey: `trudvsem:${raw.id ?? url}`,
    title,
    company: raw.company?.name?.trim() ?? "",
    url,
    city: raw.region?.name?.trim() ?? "",
    region: raw.region?.name?.trim() ?? "",
    salary: salaryOrEmpty(raw.salary ?? ""),
    publishedAt: raw["creation-date"] ? `${raw["creation-date"]}T00:00:00+03:00` : "",
    workFormat: /удален|дистанц/i.test(`${raw.schedule ?? ""} ${duty}`) ? "удалённо" : (raw.schedule ?? ""),
    employment: "",
    description: [duty, requirements].filter(Boolean).join("\n"),
  };
}

export async function searchTrudvsem(fetchImpl: FetchLike): Promise<{ report: SourceReport; vacancies: Vacancy[] }> {
  const url = new URL("https://opendata.trudvsem.ru/api/v1/vacancies/region/7700000000000");
  url.searchParams.set("text", "операционный директор");
  url.searchParams.set("offset", "0");
  url.searchParams.set("limit", "20");
  try {
    const payload = JSON.parse(await fetchText(fetchImpl, url.toString())) as {
      results?: { vacancies?: Array<{ vacancy?: TrudVacancy }> };
    };
    const vacancies = (payload.results?.vacancies ?? [])
      .map((row) => (row.vacancy ? mapTrudVacancy(row.vacancy) : null))
      .filter((item): item is Vacancy => item !== null);
    return { report: { source: "Работа России", ok: true, count: vacancies.length }, vacancies };
  } catch (error) {
    return {
      report: { source: "Работа России", ok: false, count: 0, error: error instanceof Error ? error.message : String(error) },
      vacancies: [],
    };
  }
}

type HabrCard = {
  id?: number;
  href?: string;
  title?: string;
  remoteWork?: boolean;
  publishedDate?: { date?: string };
  location?: { title?: string } | null;
  company?: { title?: string };
  employment?: string;
  salary?: { formatted?: string };
};

export function mapHabrCard(card: HabrCard): Vacancy | null {
  const title = card.title?.trim() ?? "";
  if (!title || !card.href) return null;
  const url = card.href.startsWith("http") ? card.href : `https://career.habr.com${card.href}`;
  return {
    source: "habr",
    id: String(card.id ?? vacancyIdFromUrl(url)),
    dedupeKey: `habr:${card.id ?? url}`,
    title,
    company: card.company?.title?.trim() ?? "",
    url,
    city: card.location?.title?.trim() ?? "",
    region: card.location?.title?.trim() ?? "",
    salary: card.salary?.formatted?.trim() ?? "",
    publishedAt: card.publishedDate?.date ?? "",
    workFormat: card.remoteWork ? "удалённо" : "",
    employment: card.employment === "part_time" ? "частичная занятость" : "",
    description: "",
  };
}

export async function searchHabr(fetchImpl: FetchLike): Promise<{ report: SourceReport; vacancies: Vacancy[] }> {
  const vacancies: Vacancy[] = [];
  const errors: string[] = [];
  for (const query of ["операционный директор", "COO"]) {
    const url = new URL("https://career.habr.com/vacancies");
    url.searchParams.set("q", query);
    url.searchParams.set("type", "all");
    try {
      const html = await fetchText(fetchImpl, url.toString());
      const match = html.match(/<script type="application\/json" data-ssr-state="true">([\s\S]*?)<\/script>/);
      if (!match) throw new Error("нет данных вакансий");
      const data = JSON.parse(match[1]) as { vacancies?: { list?: HabrCard[] } };
      for (const card of data.vacancies?.list ?? []) {
        const vacancy = mapHabrCard(card);
        if (vacancy) vacancies.push(vacancy);
      }
    } catch (error) {
      errors.push(error instanceof Error ? error.message : String(error));
    }
  }
  return {
    report: { source: "Хабр Карьера", ok: errors.length < 2, count: vacancies.length, error: errors[0] },
    vacancies,
  };
}

type SuperjobItem = {
  id?: number;
  profession?: string;
  firm_name?: string;
  town?: { title?: string };
  payment_from?: number;
  payment_to?: number;
  link?: string;
  date_published?: number;
  candidat?: string;
  work?: string;
  place_of_work?: { title?: string };
  type_of_work?: { title?: string };
};

function superjobSalary(item: SuperjobItem): string {
  const from = item.payment_from ?? 0;
  const to = item.payment_to ?? 0;
  if (from && to) return `от ${from.toLocaleString("ru-RU")} до ${to.toLocaleString("ru-RU")} ₽`;
  if (from) return `от ${from.toLocaleString("ru-RU")} ₽`;
  if (to) return `до ${to.toLocaleString("ru-RU")} ₽`;
  return "";
}

export function mapSuperjob(item: SuperjobItem): Vacancy | null {
  const title = item.profession?.trim() ?? "";
  if (!title || !item.id) return null;
  return {
    source: "superjob",
    id: String(item.id),
    dedupeKey: `superjob:${item.id}`,
    title,
    company: item.firm_name?.trim() ?? "",
    url: item.link?.trim() || `https://www.superjob.ru/vakansii/${item.id}.html`,
    city: item.town?.title?.trim() ?? "",
    region: item.town?.title?.trim() ?? "",
    salary: superjobSalary(item),
    publishedAt: item.date_published ? new Date(item.date_published * 1000).toISOString() : "",
    workFormat: item.place_of_work?.title?.trim() ?? "",
    employment: item.type_of_work?.title?.trim() ?? "",
    description: [item.work, item.candidat].filter(Boolean).join("\n"),
  };
}

export async function searchSuperjob(fetchImpl: FetchLike, apiKey: string | undefined): Promise<{ report: SourceReport; vacancies: Vacancy[] }> {
  if (!apiKey) {
    return { report: { source: "SuperJob", ok: true, count: 0, error: "ключ API не задан" }, vacancies: [] };
  }
  const url = new URL("https://api.superjob.ru/2.0/vacancies/");
  url.searchParams.set("keyword", "операционный директор");
  url.searchParams.set("town", "4");
  url.searchParams.set("count", "20");
  url.searchParams.set("period", "14");
  try {
    const payload = JSON.parse(await fetchText(fetchImpl, url.toString(), { "X-Api-App-Id": apiKey })) as { objects?: SuperjobItem[] };
    const vacancies = (payload.objects ?? []).map(mapSuperjob).filter((item): item is Vacancy => item !== null);
    return { report: { source: "SuperJob", ok: true, count: vacancies.length }, vacancies };
  } catch (error) {
    return {
      report: { source: "SuperJob", ok: false, count: 0, error: error instanceof Error ? error.message : String(error) },
      vacancies: [],
    };
  }
}

export async function enrichVacancy(fetchImpl: FetchLike, vacancy: Vacancy): Promise<Vacancy> {
  if (vacancy.description && vacancy.workFormat) return vacancy;
  if (vacancy.source === "trudvsem" || vacancy.source === "superjob") return vacancy;
  try {
    const html = await fetchText(fetchImpl, vacancy.url);
    const posting = parseJobPosting(html);
    const format = extractWorkFormat(html) || vacancy.workFormat;
    if (!posting && !format) return vacancy;
    return {
      ...vacancy,
      title: posting?.title || vacancy.title,
      company: pickCompany(posting?.company ?? "", vacancy.company),
      city: posting?.city || vacancy.city,
      region: posting?.region || vacancy.region,
      publishedAt: posting?.datePosted || vacancy.publishedAt,
      description: (posting?.description || vacancy.description).slice(0, 8_000),
      workFormat: format,
    };
  } catch {
    return vacancy;
  }
}

export function habrDescriptionFromHtml(html: string): string {
  return parseJobPosting(html)?.description ?? htmlToText(html).slice(0, 4_000);
}
