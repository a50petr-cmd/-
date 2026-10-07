import type { ScoredVacancy, SourceReport } from "./types.ts";
import { escapeHtml, splitText } from "./text.ts";

const SOURCE_LABEL: Record<ScoredVacancy["source"], string> = {
  hh: "hh.ru",
  zarplata: "Зарплата.ру",
  trudvsem: "Работа России",
  habr: "Хабр Карьера",
  superjob: "SuperJob",
};

export function formatVacancyMessages(vacancy: ScoredVacancy, letter: string): string[] {
  const place = [vacancy.company, vacancy.city || vacancy.region, SOURCE_LABEL[vacancy.source]].filter(Boolean);
  const lines = [`<b>${escapeHtml(vacancy.title)}</b>`, escapeHtml(place.join(" · "))];
  if (vacancy.salary) lines.push(escapeHtml(vacancy.salary));
  if (vacancy.workFormat) lines.push(escapeHtml(`Формат: ${vacancy.workFormat}`));
  lines.push(`<a href="${escapeHtml(vacancy.url)}">Открыть вакансию</a>`);
  const head = lines.join("\n");
  const body = `<b>Сопроводительное письмо</b>\n\n${escapeHtml(letter)}`;
  const combined = `${head}\n\n${body}`;
  if (combined.length <= 3900) return [combined];
  return [head, ...splitText(body, 3900)];
}

export function formatRunSummary(dateLabel: string, reports: SourceReport[], sent: number): string {
  const lines = reports.map((report) => {
    const state = report.ok ? String(report.count) : `ошибка${report.error ? `: ${report.error}` : ""}`;
    const note = report.ok && report.error ? ` (${report.error})` : "";
    return `${report.source}: ${state}${note}`;
  });
  if (sent === 0) {
    return [`На ${dateLabel} новых подходящих вакансий нет.`, "", ...lines].join("\n");
  }
  return [`Подборка на ${dateLabel}. Новых вакансий: ${sent}.`, "", ...lines].join("\n");
}

export async function sendTelegram(token: string, chatId: string, text: string, fetchImpl: typeof fetch = fetch): Promise<void> {
  const response = await fetchImpl(`https://api.telegram.org/bot${token}/sendMessage`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      chat_id: chatId,
      text,
      parse_mode: "HTML",
      link_preview_options: { is_disabled: true },
    }),
  });
  if (response.ok) return;
  const plain = await fetchImpl(`https://api.telegram.org/bot${token}/sendMessage`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      chat_id: chatId,
      text: text.replace(/<[^>]+>/g, ""),
      link_preview_options: { is_disabled: true },
    }),
  });
  if (!plain.ok) {
    throw new Error(`Telegram ${plain.status}`);
  }
}

export const helpText = [
  "Ищу вакансии операционного директора (COO) по России и готовлю сопроводительное письмо по резюме Петра Алексеева.",
  "",
  "Команды:",
  "/search — найти вакансии сейчас",
  "/status — состояние рассылки",
  "/pause — остановить ежедневную рассылку",
  "/resume — включить рассылку",
  "/help — эта справка",
  "",
  "По рабочим дням в 09:00 мск присылаю до 5 новых вакансий и письмо к каждой.",
  "Площадки: hh.ru, Зарплата.ру, Работа России, Хабр Карьера. SuperJob подключается ключом API.",
  "Отклик на вакансию сам не отправляю.",
].join("\n");
