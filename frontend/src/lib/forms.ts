import type { Schema } from "../components/SchemaForm";
export const simpleSchema = (fields: Record<string, Schema>): Schema => ({
  type: "object",
  properties: fields,
});
export const approvalSchema = simpleSchema({
  decision: { enum: ["APPROVED", "REJECTED"], default: "APPROVED" },
  comment: { type: "string", title: "Justificativa" },
});
export const submitSchema = simpleSchema({ workflow_id: { type: "string" } });
