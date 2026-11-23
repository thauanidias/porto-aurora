import { rows, str, type Row } from "../lib/api";

const fieldNames: Record<string, string> = { skills: "Competências técnicas", certifications: "Certificações", experience_years: "Experiência profissional", education_level: "Formação acadêmica", languages: "Idiomas", availability: "Disponibilidade", shift: "Turno", travel: "Disponibilidade para viagens", relocation: "Disponibilidade para mudança", test_score: "Resultado dos testes", evaluation_score: "Avaliação profissional" };
const ruleNames: Record<string, string> = { MULTI_CHOICE: "Verifica os conhecimentos ou qualificações informados", NUMBER_MIN: "Compara com o mínimo exigido", NUMBER_RANGE: "Verifica se está dentro da faixa definida", LEVEL: "Compara com o nível mínimo exigido", BOOLEAN: "Confere a condição solicitada", EXACT: "Confere a informação exigida", SINGLE_CHOICE: "Compara com a opção exigida", CUSTOM_FORMULA: "Aplica a fórmula configurada" };
const degrees: Record<string, string> = { "1": "Ensino fundamental", "2": "Ensino médio", "3": "Ensino técnico", "4": "Ensino superior", "5": "Pós-graduação", "6": "Mestrado", "7": "Doutorado" };
function expected(criterion: Row): string {
  const value = criterion.expected;
  if (value == null) return "Não definido";
  if (Array.isArray(value)) return value.join(criterion.kind === "NUMBER_RANGE" ? " a " : ", ");
  if (typeof value === "boolean") return value ? "Sim" : "Não";
  if (criterion.field === "education_level") return degrees[str(value)] ?? str(value);
  if (criterion.field === "experience_years") return `${str(value)} ano(s) de experiência`;
  return ({ CAPPED_PERCENT: "Nota de 0 a 100", BINARY_PASS: "Atendimento da condição" } as Record<string, string>)[str(value)] ?? str(value);
}

function Model({ model, current = false }: { model: Row; current?: boolean }) {
  const criteria = rows(model.criteria);
  const applicable = criteria.filter(c => !c.not_applicable);
  const totalWeight = applicable.reduce((sum, c) => sum + Number(c.weight ?? 0), 0);
  return <article className="scoring-model-summary">
    <div className="scoring-model-status"><span>{current ? "MODELO ATUAL" : "MODELO ANTERIOR"} · VERSÃO {str(model.number)}</span><strong>{applicable.length ? "Avaliação com pontuação" : "Avaliação manual pelo RH"}</strong></div>
    <p className="scoring-model-explanation">{applicable.length ? "A compatibilidade é calculada pelos critérios abaixo. O peso indica quanto cada critério influencia a nota. A decisão final continua com o RH." : "Esta vaga ainda não usa critérios para pontuação automática. O RH analisa os currículos e registra o parecer de cada candidato. Nenhuma nota deve ser interpretada como incompatibilidade nesta configuração."}</p>
    {applicable.length > 0 && <>
      <div className="scoring-model-stats"><span><strong>{applicable.length}</strong> critérios no cálculo</span><span><strong>{applicable.filter(c => c.mandatory || c.knockout).length}</strong> requisitos obrigatórios</span><span><strong>{totalWeight}%</strong> soma dos pesos aplicáveis</span></div>
      <div className="scoring-criteria-list">{applicable.map((criterion, index) => <section key={str(criterion.key)}><div className="scoring-criterion-heading"><span className="scoring-criterion-number">{index + 1}</span><div><h3>{str(criterion.name)}</h3><p>{fieldNames[str(criterion.field)] ?? "Critério profissional"}</p></div><strong className="scoring-criterion-weight">Peso {str(criterion.weight)}%</strong></div>
        <dl><div><dt>O que buscamos</dt><dd>{expected(criterion)}</dd></div><div><dt>Como será avaliado</dt><dd>{ruleNames[str(criterion.kind)] ?? "Conforme a regra definida pelo RH"}</dd></div><div><dt>Tipo de requisito</dt><dd>{criterion.mandatory || criterion.knockout ? "Obrigatório · confirmar eventuais pendências" : "Desejável"}</dd></div></dl>
        {Boolean(criterion.justification) && <p className="scoring-criterion-reason"><strong>Por que avaliar:</strong> {str(criterion.justification)}</p>}
      </section>)}</div>
    </>}
    {Boolean(model.reason) && <p className="scoring-version-reason"><strong>Registro desta versão:</strong> {str(model.reason)}</p>}
  </article>;
}

export function ScoringModelSummary({ models }: { models: Row[] }) {
  if (!models.length) return <p className="scoring-model-explanation">Nenhum modelo configurado. Defina os critérios profissionais e seus pesos para começar a comparar os candidatos.</p>;
  return <><Model model={models[0]} current />{models.length > 1 && <details className="scoring-model-history"><summary>Consultar {models.length - 1} versão(ões) anterior(es)</summary>{models.slice(1).map(model => <Model key={model.id} model={model} />)}</details>}</>;
}
