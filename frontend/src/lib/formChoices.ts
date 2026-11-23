import type { Schema } from "../components/SchemaForm";

const suggestions: Record<string, string[]> = {
  nationality: ["Brasileira", "Portuguesa", "Venezuelana", "Colombiana", "Argentina", "Boliviana", "Peruana"],
  relationship: ["Filho(a)", "Cônjuge", "Companheiro(a)", "Pai", "Mãe", "Irmão(ã)", "Enteado(a)", "Outro"],
  state: ["AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO"],
  shirt_size: ["PP", "P", "M", "G", "GG", "XG", "EXG"],
  pants_size: Array.from({ length: 17 }, (_, index) => String(32 + index * 2)),
  boot_size: Array.from({ length: 16 }, (_, index) => String(33 + index)),
  other_language: ["Alemão", "Francês", "Italiano", "Japonês", "Mandarim", "Libras"],
  education: ["Ensino fundamental incompleto", "Ensino fundamental completo", "Ensino médio incompleto", "Ensino médio completo", "Curso técnico em andamento", "Curso técnico concluído", "Ensino superior em andamento", "Ensino superior completo", "Pós-graduação", "Mestrado", "Doutorado"],
};

/** Suggestions only: preserve stored values, schema validation and free-text alternatives. */
export function withFormChoices(source: Schema, field = ""): Schema {
  const choices = source.type === "string" && !source.enum ? suggestions[field] : undefined;
  return {
    ...source,
    ...(choices ? { examples: choices, placeholder: "Digite para filtrar ou informe outra resposta" } : {}),
    ...(source.properties ? { properties: Object.fromEntries(Object.entries(source.properties).map(([key, child]) => [key, withFormChoices(child, key)])) } : {}),
    ...(source.$defs ? { $defs: Object.fromEntries(Object.entries(source.$defs).map(([key, child]) => [key, withFormChoices(child)])) } : {}),
    ...(source.items ? { items: withFormChoices(source.items, field) } : {}),
    ...(source.anyOf ? { anyOf: source.anyOf.map(child => withFormChoices(child, field)) } : {}),
  };
}
