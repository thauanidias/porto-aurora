import {expect, it} from "vitest";
import {mergeResumeValues, normalizeResumeDraft} from "./resumeMerge";

it("preserves saved and unsaved data, fills matching records and deduplicates imports", () => {
  const existing = {name: "Nome já revisado", profile: {skills: ["Excel"], education: [{course: "Administração", institution: "Faculdade", degree: "SUPERIOR"}]}};
  const imported = {name: "Nome do PDF", phone: "91999999999", profile: {skills: ["excel", "Logística"], education: [
    {course: "ADMINISTRACAO", institution: "Faculdade", period_text: "2018–2022"},
    {course: "Curso técnico", institution: "Escola"},
  ]}};
  const merged = mergeResumeValues(existing, imported);
  expect(merged).toEqual({name: "Nome já revisado", phone: "91999999999", profile: {skills: ["Excel", "Logística"], education: [
    {course: "Administração", institution: "Faculdade", degree: "SUPERIOR", period_text: "2018–2022"},
    {course: "Curso técnico", institution: "Escola"},
  ]}});
  expect(mergeResumeValues(merged, imported)).toEqual(merged);
  expect(existing.profile.skills).toEqual(["Excel"]);
});

it("keeps separate jobs when explicit periods differ", () => {
  const before = [{company: "Empresa", position: "Analista", start: "2020-01-01"}];
  expect(mergeResumeValues(before, [{company: "Empresa", position: "Analista", start: "2023-01-01"}], "experiences")).toHaveLength(2);
});

it("submits unknown dates and levels as null rather than invented defaults", () => {
  expect(normalizeResumeDraft({type: "object", properties: {start: {anyOf: [{type: "string", format: "date"}, {type: "null"}]}, level: {anyOf: [{type: "integer"}, {type: "null"}]}}}, {start: "", level: ""})).toEqual({start: null, level: null});
});
