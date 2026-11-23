import { obj, rows, str, type Row } from "../lib/api";
import { label } from "../lib/labels";
import { BriefcaseBusiness, GraduationCap, Award, Wrench } from "lucide-react";

function qualification(value: unknown) {
  const names: Record<string, string> = { COMPLETED: "Concluída", IN_PROGRESS: "Em andamento", CONCLUIDO: "Concluído", CURSANDO: "Em andamento", INTERROMPIDO: "Interrompido", FUNDAMENTAL: "Ensino fundamental", MEDIO: "Ensino médio", TECNICO: "Ensino técnico", SUPERIOR: "Ensino superior", POS: "Pós-graduação", MESTRADO: "Mestrado", DOUTORADO: "Doutorado" };
  return names[str(value)] ?? label(str(value));
}

function monthYear(value: unknown) {
  const text = str(value);
  return /^\d{4}-\d{2}/.test(text) ? `${text.slice(5, 7)}/${text.slice(0, 4)}` : text;
}

export function CandidateScreeningProfile({ candidate }: { candidate: Row }) {
  const profile = obj(candidate.profile);
  const experiences = rows(profile.experiences);
  const education = rows(profile.education);
  const certificates = rows(profile.certifications);
  const skills = Array.isArray(profile.skills) ? profile.skills.map(str).filter(Boolean) : [];
  const hasProfile = experiences.length || education.length || skills.length || certificates.length || rows(profile.courses).length || rows(profile.languages).length;
  if (candidate.blind) return <p className="muted">Perfil restrito nesta etapa.</p>;
  return <div className="candidate-screening-profile">
    <p className="candidate-screening-position">{str(profile.desired_position) || "Resumo profissional"}</p>
    {!hasProfile && <p className="candidate-screening-missing">Perfil profissional ainda não preenchido. Consulte o currículo antes de registrar a decisão.</p>}
    {education.length > 0 && <div className="screening-profile-block"><span><GraduationCap size={17} aria-hidden="true" />FORMAÇÃO</span>{education.slice(0, 2).map((item,index) => <p key={index}><strong>{str(item.course) || qualification(item.degree)}</strong>{item.institution ? ` · ${str(item.institution)}` : ""}{item.status ? ` · ${qualification(item.status)}` : ""}</p>)}</div>}
    {experiences.length > 0 && <div className="screening-profile-block"><span><BriefcaseBusiness size={17} aria-hidden="true" />EXPERIÊNCIA</span>{experiences.slice(0, 2).map((item,index) => <p key={index}><strong>{str(item.position)}</strong>{item.company ? ` · ${str(item.company)}` : ""}{item.current ? " · Atual" : ""}</p>)}</div>}
    {skills.length > 0 && <div className="screening-profile-block screening-skills-block"><span><Wrench size={17} aria-hidden="true" />COMPETÊNCIAS</span><ul className="candidate-screening-skills">{skills.slice(0, 8).map((skill,index) => <li key={index}>{skill}</li>)}</ul></div>}
    {certificates.length > 0 && <div className="screening-profile-block"><span><Award size={17} aria-hidden="true" />CERTIFICAÇÕES</span>{certificates.slice(0, 2).map((item,index) => <p key={index}>{str(item.name)}</p>)}</div>}
    {Boolean(hasProfile) && <details><summary>Ver perfil profissional completo</summary>
      {experiences.length > 0 && <section><h4>Experiências profissionais</h4>{experiences.map((item,index) => <article key={index}><strong>{str(item.position)} · {str(item.company)}</strong><p>{monthYear(item.start)} — {item.current ? "Atual" : monthYear(item.end) || "Término não informado"}</p>{Boolean(item.description) && <p>{str(item.description)}</p>}</article>)}</section>}
      {education.length > 0 && <section><h4>Formação acadêmica</h4>{education.map((item,index) => <p key={index}>{str(item.course)} · {str(item.institution)} · {qualification(item.degree)} · {qualification(item.status)}</p>)}</section>}
      {skills.length > 8 && <section><h4>Todas as competências</h4><p>{skills.join(", ")}</p></section>}
      {certificates.length > 0 && <section><h4>Certificações</h4>{certificates.map((item,index) => <p key={index}>{str(item.name)} · {str(item.issuer)}</p>)}</section>}
      {rows(profile.courses).length > 0 && <section><h4>Cursos complementares</h4>{rows(profile.courses).map((item,index) => <p key={index}>{str(item.name)} · {str(item.institution)}</p>)}</section>}
      {rows(profile.languages).length > 0 && <section><h4>Idiomas</h4>{rows(profile.languages).map((item,index) => <p key={index}>{str(item.language)} · Leitura {str(item.reading)}/5 · Escrita {str(item.writing)}/5 · Conversação {str(item.speaking)}/5</p>)}</section>}
    </details>}
  </div>;
}
