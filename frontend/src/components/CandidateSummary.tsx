import { obj, str, type Row } from "../lib/api";
import { date, label } from "../lib/labels";
import { ProfilePhoto } from "./ProfilePhoto";
import { BriefcaseBusiness, GraduationCap, CalendarDays } from "lucide-react";

const names: Record<string, string> = {
  company: "Empresa",
  position: "Cargo",
  start: "Início",
  end: "Término",
  current: "Emprego atual",
  description: "Atividades",
  institution: "Instituição",
  course: "Curso",
  degree: "Escolaridade",
  status: "Situação",
  hours: "Carga horária",
  completion: "Conclusão",
  issuer: "Emissor",
  issued: "Emissão",
  expires: "Validade",
  code: "Código",
  language: "Idioma",
  reading: "Leitura",
  writing: "Escrita",
  speaking: "Conversação",
  period_text: "Período informado no currículo",
  completion_text: "Conclusão informada no currículo",
  issued_text: "Emissão informada no currículo",
  level_text: "Nível informado no currículo",
  availability: "Disponibilidade imediata",
  shift: "Turno disponível",
  travel: "Disponível para viagens",
  relocation: "Disponível para mudança",
  expected_salary: "Pretensão salarial",
  links: "Links profissionais",
  FUNDAMENTAL: "Ensino fundamental",
  MEDIO: "Ensino médio",
  TECNICO: "Técnico",
  SUPERIOR: "Superior",
  POS: "Pós-graduação",
  MESTRADO: "Mestrado",
  DOUTORADO: "Doutorado",
  CURSANDO: "Cursando",
  CONCLUIDO: "Concluído",
  INTERROMPIDO: "Interrompido",
};
function display(key: string, value: unknown): string {
  if (value == null || value === "") return "Não informado";
  if (typeof value === "boolean") return value ? "Sim" : "Não";
  if (key === "expected_salary" && typeof value === "number")
    return value.toLocaleString("pt-BR", {
      style: "currency",
      currency: "BRL",
    });
  const text = str(value);
  if (key === "Telefone") {
    const digits = text.replace(/\D/g, "").replace(/^55(?=\d{10,11}$)/, "");
    if (/^\d{10,11}$/.test(digits)) return `(${digits.slice(0, 2)}) ${digits.slice(2, -4)}-${digits.slice(-4)}`;
  }
  if (/^\d{4}-\d{2}-\d{2}$/.test(text))
    return text.split("-").reverse().join("/");
  return names[text] ?? text;
}
function Fields({ data }: { data: Record<string, unknown> }) {
  return (
    <dl className="candidate-fields">
      {Object.entries(data).map(([key, value]) => (
        <div key={key}>
          <dt>{names[key] ?? label(key)}</dt>
          <dd className={value == null || value === "" ? "muted" : undefined}>
            {key === "E-mail" && value ? <a href={"mailto:" + str(value)}>{str(value)}</a> : key === "Telefone" && value ? <a href={"tel:" + str(value).replace(/[^\d+]/g, "")}>{display(key, value)}</a> : display(key, value)}
          </dd>
        </div>
      ))}
    </dl>
  );
}

function ProfessionalEntry({ kind, data }: { kind: string; data: Record<string, unknown> }) {
  const experience = kind === "experiences";
  const education = kind === "education";
  if (!experience && !education) return <div className="candidate-profile-entry"><Fields data={Object.fromEntries(Object.entries(data).filter(([field]) => field !== "document_id"))} /></div>;
  const start = data.start ? display("start", data.start) : "";
  const end = experience && data.current === true ? "Atual" : data.end ? display("end", data.end) : "";
  const period = start && end ? `${start} a ${end}` : start ? `Início: ${start}` : end ? `Término: ${end}` : str(data.period_text || data.completion_text || (data.completion ? display("completion", data.completion) : ""));
  const title = experience ? str(data.position) || "Cargo não informado" : str(data.course) || display("degree", data.degree);
  const subtitle = experience ? str(data.company) : str(data.institution);
  const hidden = new Set(["document_id", "position", "company", "course", "institution", "start", "end", "current", "description", "status", "degree", "completion"]);
  if (period === data.period_text || period === data.completion_text) { hidden.add("period_text"); hidden.add("completion_text"); }
  const remaining = Object.fromEntries(Object.entries(data).filter(([key, value]) => !hidden.has(key) && value != null && value !== ""));
  const Icon = experience ? BriefcaseBusiness : GraduationCap;
  return <article className="professional-entry-card"><header><span className="professional-entry-icon"><Icon size={21} aria-hidden="true" /></span><div><h4>{title}</h4>{subtitle && <p>{subtitle}</p>}</div>{experience && data.current === true ? <span className="professional-entry-status">Emprego atual</span> : education && Boolean(data.status) ? <span className="professional-entry-status">{display("status", data.status)}</span> : null}</header>
    {period && <p className="professional-entry-period"><CalendarDays size={15} aria-hidden="true" />{period}</p>}
    {education && Boolean(data.degree) && str(data.course) && <p className="professional-entry-degree">{display("degree", data.degree)}</p>}
    {Boolean(data.description) && <div className="professional-entry-description"><strong>{experience ? "Atividades desenvolvidas" : "Informações complementares"}</strong><p>{str(data.description)}</p></div>}
    {Object.keys(remaining).length > 0 && <Fields data={remaining} />}
  </article>;
}
export function CandidateSummary({ candidate }: { candidate: Row }) {
  const profile = obj(candidate.profile);
  const sections = [
    ["experiences", "Experiência profissional"],
    ["education", "Formação acadêmica"],
    ["courses", "Cursos"],
    ["certifications", "Certificações"],
    ["languages", "Idiomas"],
    ["skills", "Competências"],
  ];
  const hasProfessionalData = Object.values(profile).some((value) =>
    Array.isArray(value)
      ? value.length > 0
      : value != null && value !== "" && value !== false,
  );
  return (
    <div className="candidate-summary">
      <section
        className="surface padded candidate-contact"
        aria-labelledby="candidate-contact-title"
      >
        <div className="candidate-section-heading">
          {!candidate.blind && <ProfilePhoto candidateId={candidate.id} name={str(candidate.name)} />}
          <div>
            <h2 id="candidate-contact-title">Dados pessoais e contato</h2>
            <p className="muted">Informações fornecidas no cadastro.</p>
          </div>
        </div>
        <Fields
          data={{
            "Nome completo": candidate.name,
            "Nome social": candidate.social_name,
            "E-mail": candidate.email,
            Telefone: candidate.phone,
            Localização: [candidate.city, candidate.state, candidate.country === "BR" ? "Brasil" : candidate.country].filter(Boolean).join(" · "),
          }}
        />
      </section>
      <section
        className="surface padded candidate-registration-card"
        aria-labelledby="candidate-registration-title"
      >
        <h2 id="candidate-registration-title">Sobre o cadastro</h2>
        <Fields
          data={{
            Origem:
              (
                {
                  PORTAL: "Portal de carreiras",
                  IMPORT: "Importação",
                  IMPORTED: "Importação",
                  REFERRAL: "Indicação",
                } as Record<string, string>
              )[str(candidate.source)] ?? candidate.source,
            "Cadastrado em": date(candidate.created_at),
            "Última atualização": date(candidate.updated_at),
          }}
        />

        {Boolean(candidate.talent_consent_until) && (
          <p className="muted">
            Consentimento para o banco de talentos até{" "}
            {date(candidate.talent_consent_until)}.
          </p>
        )}
        {Boolean(candidate.anonymized_at) && (
          <p className="muted">
            Cadastro anonimizado em {date(candidate.anonymized_at)}.
          </p>
        )}
        {Boolean(candidate.merged_into_id) && (
          <p className="muted">
            Este cadastro foi unificado com outro registro.
          </p>
        )}
      </section>
      <section
        className="surface padded candidate-professional"
        aria-labelledby="candidate-professional-title"
      >
        <h2 id="candidate-professional-title">Perfil profissional</h2>
        {!hasProfessionalData ? (
          <div className="candidate-profile-empty">
            <strong>Perfil profissional ainda não preenchido</strong>
            <p>
              Experiências, formação e competências aparecerão aqui quando forem
              informadas pelo candidato.
            </p>
          </div>
        ) : (
          <>
            {sections.map(([key, title]) =>
              Array.isArray(profile[key]) && profile[key].length > 0 ? (
                <div className="candidate-profile-section" key={key}>
                  <h3>{title}</h3>
                  {profile[key].map((item: unknown, index: number) =>
                    typeof item === "object" && item ? (
                      <ProfessionalEntry key={index} kind={key} data={obj(item)} />
                    ) : (
                      <span className="tag" key={index}>
                        {str(item)}
                      </span>
                    ),
                  )}
                </div>
              ) : null,
            )}
            <Fields
              data={Object.fromEntries(
                [
                  "availability",
                  "shift",
                  "travel",
                  "relocation",
                  "expected_salary",
                ]
                  .filter((key) => key in profile)
                  .map((key) => [key, profile[key]]),
              )}
            />
            {Array.isArray(profile.links) && profile.links.length > 0 && (
              <div className="candidate-profile-section">
                <h3>Links profissionais</h3>
                {profile.links.map((link: unknown, index: number) => (
                  <p key={index}>
                    {/^https?:\/\//i.test(str(link)) ? (
                      <a
                        href={str(link)}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        {str(link)}
                      </a>
                    ) : (
                      str(link)
                    )}
                  </p>
                ))}
              </div>
            )}
          </>
        )}
      </section>
    </div>
  );
}
