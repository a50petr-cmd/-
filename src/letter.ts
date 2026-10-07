import { achievements, profile, themePatterns, type Theme } from "./profile.ts";
import type { Contacts, ScoredVacancy } from "./types.ts";

const bridges: Record<Theme, string> = {
  import:
    "Последние полтора года я операционно запускал и масштабировал оптовый импорт в X5 Group: логистика, закупка и экономика направления.",
  ecommerce: "Запускал с нуля сервисы доставки и интернет-магазины и отвечал за их юнит-экономику и рост заказов.",
  franchise: "Строил франчайзинговые сети от модели окупаемости и P&L до открытия магазинов и дарксторов.",
  darkstore: "Выстраивал операционку быстрой доставки и дарксторов: сборка, логистика, ФОТ и списания.",
  b2b: "Развивал B2B-направления в ритейле: крупные клиенты, ассортимент и экономика сделки.",
  pnl: "Управляю экономикой направления: выручка, EBITDA, бюджет и операционные расходы.",
  team: "Собираю кросс-функциональные команды и перевожу стратегию в KPI, роли и регулярный операционный контур.",
};

function dominantThemes(vacancy: ScoredVacancy): Theme[] {
  const text = `${vacancy.title}\n${vacancy.description}\n${vacancy.workFormat}`;
  return (Object.keys(themePatterns) as Theme[])
    .map((theme) => ({ theme, hit: themePatterns[theme].test(text) }))
    .filter((item) => item.hit)
    .map((item) => item.theme);
}

function selectAchievements(themes: Theme[]): string[] {
  const ranked = achievements
    .map((item, index) => ({
      item,
      index,
      score: item.themes.filter((theme) => themes.includes(theme)).length,
    }))
    .sort((a, b) => b.score - a.score || a.index - b.index);

  const picked = ranked.filter((item) => item.score > 0).slice(0, 3);
  const selected = picked.length >= 2 ? picked : ranked.slice(0, 3);
  return selected.map((item) => item.item.text);
}

function clipSentence(value: string): string {
  const clean = value.replace(/\s+/g, " ").trim();
  if (clean.length <= 240) return clean;
  const cut = clean.lastIndexOf(" ", 240);
  return `${clean.slice(0, cut > 80 ? cut : 240).trim()}…`;
}

function vacancyFocus(description: string): string {
  const clean = description
    .replace(/[\u200b\u200c\u200d\ufeff\u00a0]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  if (clean.length < 40) return "";
  const marker = clean.search(/ваши задачи|обязанности|вам предстоит|что нужно делать|задачи:/i);
  const source = marker >= 0 ? clean.slice(marker) : clean;
  const sentence =
    source.split(/(?<=[.!])\s+/).find((part) => part.length >= 40 && part.length <= 260) ?? source;
  return clipSentence(sentence);
}

function availability(vacancy: ScoredVacancy): string {
  const moscow = /москва|московск/i.test(`${vacancy.city} ${vacancy.region}`);
  if (!moscow && vacancy.remote) {
    return "Готов вести роль удалённо из Москвы, к командировкам готов. Переезд не рассматриваю.";
  }
  return "Нахожусь в Москве и рассматриваю полную занятость: офис, гибрид и удалённый формат. К командировкам готов, переезд не рассматриваю.";
}

function signature(contacts: Contacts): string {
  const lines = ["С уважением,", profile.name, profile.city];
  if (contacts.phone) lines.push(contacts.phone);
  if (contacts.email) lines.push(contacts.email);
  if (contacts.telegram) lines.push(contacts.telegram);
  return lines.join("\n");
}

export function coverLetter(vacancy: ScoredVacancy, contacts: Contacts): string {
  const themes = dominantThemes(vacancy);
  const bridge =
    (themes[0] && bridges[themes[0]]) ||
    `Больше ${profile.experienceYears} лет запускаю и масштабирую операционные контуры в рознице, e-grocery и B2B: от P&L и процессов до команды.`;
  const company = vacancy.company ? ` в ${vacancy.company}` : "";
  const focus = vacancyFocus(vacancy.description);
  const points = selectAchievements(themes).map((text) => `— ${text}`).join("\n\n");

  return [
    "Здравствуйте!",
    "",
    `Меня зовут ${profile.shortName}, откликаюсь на вакансию «${vacancy.title}»${company}.`,
    ...(focus ? [`В описании роли для меня главное: ${focus}`] : []),
    bridge,
    "",
    "Коротко о результате:",
    points,
    "",
    availability(vacancy),
    "Буду рад коротко созвониться и обсудить, как этот опыт закроет задачи роли.",
    "",
    signature(contacts),
  ].join("\n");
}
