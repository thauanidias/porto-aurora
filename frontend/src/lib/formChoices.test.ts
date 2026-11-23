import { expect, it } from "vitest";
import { withFormChoices } from "./formChoices";
import type { Schema } from "../components/SchemaForm";

it("adds searchable suggestions without changing stored values or allowed answers", () => {
  const schema: Schema = { type: "object", properties: { education: { type: "string", maxLength: 2000 }, state: { type: "string", maxLength: 2 }, name: { type: "string" }, marital_status: { type: "string", enum: ["Solteiro", "Casado"] } } };
  const updated = withFormChoices(schema);
  expect(updated.properties?.education.examples).toContain("Ensino médio completo");
  expect(updated.properties?.state.examples).toContain("PA");
  expect(updated.properties?.name.examples).toBeUndefined();
  expect(updated.properties?.marital_status.enum).toEqual(["Solteiro", "Casado"]);
  expect(updated.properties?.education.default).toBeUndefined();
  expect(schema.properties?.education.examples).toBeUndefined();
});
it("supports nested definitions and nullable fields in the external sheet", () => {
  const updated = withFormChoices({ $defs: { Dependent: { properties: { relationship: { type: "string" } } }, ComplementaryDetails: { properties: { shirt_size: { anyOf: [{ type: "string" }, { type: "null" }] } } } } });
  expect(updated.$defs?.Dependent.properties?.relationship.examples).toContain("Filho(a)");
  expect(updated.$defs?.ComplementaryDetails.properties?.shirt_size.anyOf?.[0].examples).toContain("GG");
});
