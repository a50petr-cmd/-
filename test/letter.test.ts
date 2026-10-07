import assert from "node:assert/strict";
import test from "node:test";
import { coverLetter } from "../src/letter.ts";
import type { ScoredVacancy } from "../src/types.ts";

const vacancy: ScoredVacancy = {
  source: "hh",
  id: "1",
  dedupeKey: "board:1",
  title: "Операционный директор (COO)",
  company: "Север Импорт",
  url: "https://hh.ru/vacancy/1",
  city: "Москва",
  region: "Москва",
  salary: "",
  publishedAt: "2026-10-06T10:00:00+03:00",
  workFormat: "гибрид",
  employment: "",
  description: "Нужен руководитель импортных поставок, склада и логистики. Ответственность за EBITDA.",
  score: 90,
  remote: true,
};

test("letter uses the vacancy and a matching achievement without inventing a phone", () => {
  const letter = coverLetter(vacancy, { telegram: "https://t.me/PetroAlekseev" });
  assert.match(letter, /Север Импорт/);
  assert.match(letter, /Операционный директор \(COO\)/);
  assert.match(letter, /В описании роли для меня главное: Нужен руководитель импортных поставок/);
  assert.match(letter, /X5 Group/);
  assert.match(letter, /10–15%/);
  assert.match(letter, /t\.me\/PetroAlekseev/);
  assert.doesNotMatch(letter, /\+7/);
  assert.doesNotMatch(letter, /@/);
});

test("focus starts at the task list and does not cut a word", () => {
  const letter = coverLetter(
    {
      ...vacancy,
      description: `Компания производит оборудование. Ваши задачи: формирование стратегии развития производственных мощностей и защита инвестиционных проектов CAPEX на расширение цеха.`,
    },
    { telegram: "https://t.me/PetroAlekseev" },
  );
  assert.match(letter, /В описании роли для меня главное: Ваши задачи: формирование стратегии/);
  assert.doesNotMatch(letter, /Компания производит оборудование/);
});

test("letter adds phone and email only from contacts", () => {
  const letter = coverLetter(vacancy, { phone: "+7 000 000-00-00", email: "person@example.com", telegram: "https://t.me/PetroAlekseev" });
  assert.match(letter, /\+7 000 000-00-00/);
  assert.match(letter, /person@example.com/);
});
