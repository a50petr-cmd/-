import assert from "node:assert/strict";
import test from "node:test";
import { rankVacancies, titleScore } from "../src/match.ts";
import type { Vacancy } from "../src/types.ts";

const now = Date.parse("2026-10-07T06:00:00Z");

function vacancy(patch: Partial<Vacancy>): Vacancy {
  return {
    source: "hh",
    id: "1",
    dedupeKey: "board:1",
    title: "Операционный директор (COO)",
    company: "Пример",
    url: "https://hh.ru/vacancy/1",
    city: "Москва",
    region: "Москва",
    salary: "",
    publishedAt: "2026-10-06T10:00:00+03:00",
    workFormat: "гибрид",
    employment: "",
    description: "Управление операционным контуром, P&L и логистикой.",
    ...patch,
  };
}

test("title score prefers COO and drops junior roles", () => {
  assert.ok(titleScore("Операционный директор (COO)") >= 60);
  assert.equal(titleScore("Помощник операционного директора"), 0);
  assert.equal(titleScore("Курьер"), 0);
  assert.ok(titleScore("Коммерческий директор") < 30);
});

test("keeps a moscow COO and drops an office role outside moscow", () => {
  const ranked = rankVacancies(
    [
      vacancy({}),
      vacancy({
        id: "2",
        dedupeKey: "board:2",
        title: "Операционный директор",
        city: "Казань",
        region: "Татарстан",
        workFormat: "на месте работодателя",
      }),
      vacancy({
        id: "3",
        dedupeKey: "board:3",
        title: "Операционный директор",
        city: "Казань",
        region: "Татарстан",
        workFormat: "удалённо",
      }),
    ],
    { now, periodDays: 14, minScore: 78, limit: 5 },
  );
  assert.deepEqual(ranked.map((item) => item.id), ["1", "3"]);
});

test("drops a vacancy that is an assistant role in the description", () => {
  const ranked = rankVacancies(
    [vacancy({ description: "Операционный директор, ассистент руководителя по проектам." })],
    { now, periodDays: 14, minScore: 78, limit: 5 },
  );
  assert.equal(ranked.length, 0);
});

test("drops a COO role in a distant industry", () => {
  const ranked = rankVacancies(
    [
      vacancy({
        title: "Операционный директор (отделка квартир)",
        description: "Управление стройкой и отделкой квартир у застройщика.",
      }),
    ],
    { now, periodDays: 14, minScore: 78, limit: 5 },
  );
  assert.equal(ranked.length, 0);
});
