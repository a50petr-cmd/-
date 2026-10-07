import { achievements, profile, themePatterns, type Achievement, type Theme } from "./profile.ts";
import type { Contacts, ScoredVacancy } from "./types.ts";

function dominantThemes(vacancy: ScoredVacancy): Theme[] {
  const text = `${vacancy.title}\n${vacancy.description}\n${vacancy.workFormat}`;
  return (Object.keys(themePatterns) as Theme[])
    .map((theme) => ({ theme, hit: themePatterns[theme].test(text) }))
    .filter((item) => item.hit)
    .map((item) => item.theme);
}

function selectAchievements(themes: Theme[]): Achievement[] {
  const ranked = achievements
    .map((item, index) => ({
      item,
      index,
      score: item.themes.filter((theme) => themes.includes(theme)).length,
    }))
    .sort((a, b) => b.score - a.score || a.index - b.index);
  const matched = ranked.filter((item) => item.score > 0).slice(0, 2);
  const selected = matched.length > 0 ? matched : ranked.slice(0, 2);
  return selected.map((item) => item.item);
}

function closing(vacancy: ScoredVacancy): string {
  const moscow = /москва|московск/i.test(`${vacancy.city} ${vacancy.region}`);
  if (!moscow && vacancy.remote) {
    return "Могу вести роль удалённо из Москвы. Переезд не рассматриваю, к командировкам готов. Если отклик подойдёт, давайте созвонимся.";
  }
  return "Я в Москве, смотрю офис, гибрид и удалёнку. Если отклик подойдёт, давайте созвонимся.";
}

function signature(contacts: Contacts): string {
  const lines = ["С уважением,", profile.name, profile.city];
  if (contacts.phone) lines.push(contacts.phone);
  if (contacts.email) lines.push(contacts.email);
  if (contacts.telegram) lines.push(contacts.telegram);
  return lines.join("\n");
}

export function coverLetter(vacancy: ScoredVacancy, contacts: Contacts): string {
  const [lead, extra] = selectAchievements(dominantThemes(vacancy));
  const company = vacancy.company ? ` в ${vacancy.company}` : "";
  return [
    "Здравствуйте!",
    "",
    `Меня зовут ${profile.shortName}. Откликаюсь на «${vacancy.title}»${company}.`,
    "",
    lead?.text ?? "",
    ...(extra ? ["", extra.text] : []),
    "",
    closing(vacancy),
    "",
    signature(contacts),
  ]
    .filter((line, index, lines) => line !== "" || lines[index - 1] !== "")
    .join("\n");
}
