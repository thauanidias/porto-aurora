const empty = (value: unknown) => value == null || value === "";
const normalized = (value: unknown) => String(value ?? "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").trim().toLocaleLowerCase("pt-BR").replace(/\s+/g, " ");
const identities: Record<string, string[]> = {
  experiences: ["company", "position", "start", "end", "period_text"], education: ["course", "institution", "start"],
  courses: ["name", "institution"], certifications: ["name", "issuer"], languages: ["language"],
};

/** Fill gaps in the live draft, preserving existing and unsaved values. */
export function mergeResumeValues(current: unknown, incoming: unknown, group = ""): unknown {
  if (empty(incoming)) return current;
  if (Array.isArray(incoming)) {
    const result: unknown[] = Array.isArray(current) ? [...current] : [];
    for (const item of incoming) {
      const object = item !== null && typeof item === "object" && !Array.isArray(item);
      const keys = identities[group] ?? [];
      const index = result.findIndex(value => {
        if (!object) return typeof value !== "object" && normalized(value) === normalized(item);
        if (!value || typeof value !== "object" || Array.isArray(value)) return false;
        const left = value as Record<string, unknown>, right = item as Record<string, unknown>;
        return keys.some(key => !empty(left[key]) && !empty(right[key])) && keys.every(key => empty(left[key]) || empty(right[key]) || normalized(left[key]) === normalized(right[key]));
      });
      if (index < 0) result.push(item);
      else if (object) result[index] = mergeResumeValues(result[index], item, group);
    }
    return result;
  }
  if (typeof incoming === "object" && incoming !== null) {
    const result = current && typeof current === "object" && !Array.isArray(current) ? {...current as Record<string, unknown>} : {};
    for (const [key, value] of Object.entries(incoming)) result[key] = mergeResumeValues(result[key], value, key);
    return result;
  }
  return empty(current) ? incoming : current;
}
import type { Schema } from "../components/SchemaForm";


export function normalizeResumeDraft(schema: Schema | undefined, value: unknown, root = schema): unknown {
  if (!schema) return value;
  if (schema.$ref) return normalizeResumeDraft(root?.$defs?.[schema.$ref.split("/").at(-1) ?? ""], value, root);
  if (schema.anyOf) {
    if (schema.anyOf.some(item => item.type === "null") && empty(value)) return null;
    return normalizeResumeDraft(schema.anyOf.find(item => item.type !== "null"), value, root);
  }
  if (Array.isArray(value)) return value.map(item => normalizeResumeDraft(schema.items, item, root));
  if (value && typeof value === "object") return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, normalizeResumeDraft(schema.properties?.[key], item, root)]));
  if (["integer", "number"].includes(schema.type ?? "") && value !== "" && value != null) return Number(value);
  return value;
}
