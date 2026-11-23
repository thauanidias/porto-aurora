import { JobEnrollment } from "../components/JobEnrollment";
import { Brand } from "../components/Brand";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  ArrowUpRight,
  Building2,
  BriefcaseBusiness,
  Clock3,
  MapPin,
  Search,
  Share2,
  UserPlus,
  Users,
} from "lucide-react";
import {
  api,
  post,
  obj,
  rows,
  str,
  type Collection,
  type Row,
} from "../lib/api";
import { label } from "../lib/labels";
import { useSession } from "../lib/session";
import { Empty, ErrorBox, Modal } from "../components/ui";

export function PublicHeader({ showActions = false, internalPortal = false }: { showActions?: boolean; internalPortal?: boolean }) {
  const session = useSession();
  const areaAvailable = Boolean(session.data);
  return (
    <header className="public-header">
      <Link to={internalPortal ? "/oportunidades-internas" : "/carreiras"} className="brand">
        <Brand />
      </Link>
      {showActions && !internalPortal && <nav>
        {!internalPortal && <Link
          to={areaAvailable ? "/candidato" : "/entrar"}
          className="button small"
        >
          {areaAvailable ? "Minha área" : "Área do candidato"}
          <ArrowUpRight size={16} />
        </Link>}
      </nav>}
    </header>
  );
}
export function CareersPage({ internal = false }: { internal?: boolean }) {
  const session = useSession();
  const employeeAccess = Boolean(session.data?.permissions?.includes("internal.view"));
  const [q, setQ] = useState("");
  const [pageNumber, setPageNumber] = useState(1);
  const [city, setCity] = useState("");
  const [modality, setModality] = useState("");

  const query = useQuery({
    queryKey: ["careers", q, city, modality, internal, pageNumber],
    queryFn: () =>
      api<Collection>(
        (internal ? "/public/internal-vacancies" : "/public/vacancies") +
          "?" +
          new URLSearchParams({
            q,
            city,
            modality,
            page_number: String(pageNumber),
          }),
      ),
  });
  return (
    <div className="careers careers-home" data-portal={internal ? "internal" : "external"}>
      <PublicHeader showActions internalPortal={internal} />
      <main>
        <section className="career-hero">
          <div className="hero-copy">
            <p className="eyebrow">
              {internal ? "OPORTUNIDADES INTERNAS" : "CARREIRAS NO PORTO AURORA"}
            </p>
            <h1>
              <span>Novos horizontes.</span>
              <span className="hero-title-accent">Sua próxima jornada.</span>
            </h1>
            <p>
              {internal ? "Você já faz parte da nossa história. Explore novas oportunidades no terminal e dê o próximo passo na sua carreira dentro do Porto Aurora." : 
                "Construa sua trajetória no Porto Aurora, uma empresa portuária fictícia. Encontre oportunidades e dê o próximo passo na sua carreira."}
            </p>
            <div className="hero-actions">
              <a className="hero-link" href="#oportunidades">
                Ver oportunidades <ArrowRight size={19} />
              </a>
              <Link className="hero-register-link" to={internal ? employeeAccess ? "/candidato/perfil#ficha-interna" : "/cadastro-colaborador" : "/cadastro"}>
                {internal && employeeAccess ? "Minha ficha interna" : "Criar minha conta"} <ArrowUpRight size={17} />
              </Link>
            </div>
          </div>

        </section>
        {internal && <section className="internal-portal-access" aria-labelledby="employee-access-title">
          <div className="section-heading"><div><p className="eyebrow">PORTAL INTERNO Porto Aurora</p><h2 id="employee-access-title">{internal ? "Acesse sua área" : "Já faz parte do Porto Aurora?"}</h2></div></div>
          <div className="internal-portal-access-grid">
            <Link className="internal-portal-access-card" to="/cadastro-colaborador" aria-label="Fazer inscrição de colaborador"><UserPlus size={25} aria-hidden="true" /><h3>Inscrição do colaborador</h3><p>Primeiro acesso? Cadastre seu e-mail pessoal ou corporativo e complete sua ficha interna.</p><span>Fazer minha inscrição <ArrowRight size={17} aria-hidden="true" /></span></Link>
            <Link className="internal-portal-access-card" to={employeeAccess ? "/candidato" : "/entrar-colaborador"} aria-label="Entrar na área do colaborador"><BriefcaseBusiness size={25} aria-hidden="true" /><h3>Área do colaborador</h3><p>Acesse sua ficha interna, as vagas e o acompanhamento das suas candidaturas.</p><span>Acessar minha área <ArrowRight size={17} aria-hidden="true" /></span></Link>
            <Link className="internal-portal-access-card" to="/entrar-gestor" aria-label="Entrar na área dos gestores"><Users size={25} aria-hidden="true" /><h3>Área dos gestores</h3><p>Solicite contratações e acompanhe as seleções da sua equipe.</p><span>Acessar como gestor <ArrowRight size={17} aria-hidden="true" /></span></Link>
          </div>
        </section>}
        <section className="jobs-section" id="oportunidades">
          <div className="section-heading">
            <div>
              <p className="eyebrow">ENCONTRE SEU PRÓXIMO PASSO</p>
              <h2>{internal ? "Oportunidades internas" : "Oportunidades abertas"}</h2>
            </div>
            <span className="career-opportunity-count" aria-live="polite">
              {query.isPending ? "Buscando vagas…" : query.isError ? "Consulta indisponível" : `${query.data?.total ?? 0} ${(query.data?.total ?? 0) === 1 ? "oportunidade" : "oportunidades"}`}
            </span>
          </div>
          <div className="job-search">
            <label className="field career-search-label"><span>Cargo ou palavra-chave</span><div className="search-field">
              <Search size={20} aria-hidden="true" />
              <input
                aria-label={internal ? "Buscar vagas internas" : "Buscar oportunidades"}
                placeholder="Busque por cargo ou palavra-chave"
                value={q}
                onChange={(e) => {
                  setQ(e.target.value);
                  setPageNumber(1);
                }}
              />
            </div></label>
            <label className="field">
              <span>Cidade</span>
              <input
                value={city}
                placeholder="Todas as cidades"
                onChange={(e) => {
                  setCity(e.target.value);
                  setPageNumber(1);
                }}
              />
            </label>
            <label className="field">
              <span>Modalidade</span>
              <select
                value={modality}
                onChange={(e) => {
                  setModality(e.target.value);
                  setPageNumber(1);
                }}
              >
                <option value="">Todas</option>
                <option value="PRESENCIAL">Presencial</option>
                <option value="HIBRIDO">Híbrido</option>
                <option value="REMOTO">Remoto</option>
              </select>
            </label>
          </div>
          {(q || city || modality) && <div className="career-filter-summary"><span>Resultados para os filtros selecionados</span><button className="text-button" onClick={() => { setQ(""); setCity(""); setModality(""); setPageNumber(1); }}>Limpar filtros</button></div>}
          <ErrorBox error={query.error} />
          {query.isPending ? (
            <p role="status">Buscando oportunidades…</p>
          ) : query.isError ? <section className="surface padded"><p>Não foi possível consultar as oportunidades. Tente novamente.</p><button className="button secondary" onClick={() => void query.refetch()}>Tentar novamente</button></section> : query.data?.items.length ? (
            <div className="job-list">
              {query.data.items.map((job) => (
                <Link
                  className="job-row"
                  key={job.id}
                  aria-label={internal ? "Ver vaga " + str(job.title) : undefined}
                  to={
                    (internal
                      ? "/oportunidades-internas/"
                      : "/carreiras/vagas/") + str(job.slug)
                  }
                >
                  <div>
                    <div className="job-code"><BriefcaseBusiness size={14} aria-hidden="true" />{internal ? "OPORTUNIDADE INTERNA" : "OPORTUNIDADE Porto Aurora"}<span>{str(job.code)}</span></div>
                    <h3>{str(job.title)}</h3>
                    <div className="job-meta">
                      <span>
                        <MapPin size={16} />
                        {str(job.city)} · {str(job.state)}
                      </span>
                      <span>
                        <Building2 size={16} />
                        {label(str(job.modality))}
                      </span>
                      <span>
                        <Clock3 size={16} />
                        {label(str(job.contract_type))}
                      </span>
                    </div>
                  </div>
                  <span className="career-job-action">Ver oportunidade<ArrowUpRight size={19} aria-hidden="true" /></span>
                </Link>
              ))}
            </div>
          ) : (
            <Empty title={q || city || modality ? "Nenhuma oportunidade encontrada" : "Nenhuma oportunidade disponível neste momento"}>
              {q || city || modality ? "Tente outro cargo, cidade ou modalidade, ou limpe os filtros para consultar todas as vagas." : "Cadastre seu perfil e acompanhe novas oportunidades por aqui."}
            </Empty>
          )}
          {(query.data?.total ?? 0) > 25 && (
            <div className="toolbar">
              <button
                className="button secondary small"
                disabled={pageNumber === 1}
                onClick={() => setPageNumber(pageNumber - 1)}
              >
                Anterior
              </button>
              <span>
                Página {pageNumber} de{" "}
                {Math.ceil((query.data?.total ?? 0) / 25)}
              </span>
              <button
                className="button secondary small"
                disabled={pageNumber * 25 >= (query.data?.total ?? 0)}
                onClick={() => setPageNumber(pageNumber + 1)}
              >
                Próxima
              </button>
            </div>
          )}
          <div className="talent-invitation">
            <div>
              <h3>{internal && employeeAccess ? "Deixe sua trajetória em dia." : "Seu próximo desafio pode estar por aqui."}</h3>
              <p>
                {internal ? employeeAccess ? "Confira sua ficha interna, suas experiências e seu currículo antes de se candidatar." : "Cadastre-se com seu e-mail pessoal ou corporativo para completar sua ficha interna e participar das seleções." : "Cadastre seu perfil e autorize sua participação no banco de talentos."}
              </p>
            </div>
            <Link className="button secondary" to={internal ? employeeAccess ? "/candidato/perfil#ficha-interna" : "/cadastro-colaborador" : "/candidato/privacidade"}>
              {internal ? employeeAccess ? "Atualizar ficha interna" : "Criar minha conta" : "Participar do banco"} <ArrowRight size={17} />
            </Link>
          </div>
        </section>
      </main>
      <footer className="public-footer">
        <span>{internal ? "Porto Aurora Talentos · Portal interno" : "Porto Aurora"}</span>
        <span className="public-footer-links">{internal && <Link to="/entrar-gestor">Área do gestor</Link>}<Link to="/privacidade">Privacidade e termos</Link></span>
      </footer>
    </div>
  );
}
export function JobPage({
  internal = false,
  invitation = false,
}: {
  internal?: boolean;
  invitation?: boolean;
}) {
  const [inviteToken] = useState(
    () => new URLSearchParams(location.hash.slice(1)).get("token") ?? "",
  );
  const { slug } = useParams();
  const session = useSession();
  const navigate = useNavigate();
  const [open, setOpen] = useState(() => new URLSearchParams(location.search).get("candidatar") === "1");
  const [confirmation, setConfirmation] = useState("");
  const [error, setError] = useState<unknown>();
  const query = useQuery({
    queryKey: ["job", slug, internal, invitation, inviteToken],
    queryFn: () =>
      invitation
        ? post<Row>("/public/invitations/lookup", { token: inviteToken })
        : api<Row>(
            (internal ? "/internal/vacancies/" : "/public/vacancies/") + slug,
          ),
  });
  if (query.isPending)
    return (
      <>
        <PublicHeader internalPortal={internal} />
        <main className="narrow-page" role="status">
          Carregando oportunidade…
        </main>
      </>
    );
  if (query.error || !query.data)
    return (
      <>
        <PublicHeader internalPortal={internal} />
        <main className="narrow-page">
          <ErrorBox error={query.error} />
        </main>
      </>
    );
  const job = query.data;
  const details = obj(job.details);
  return (
    <>
      <PublicHeader internalPortal={internal} />
        <main className="job-detail job-detail-modern">
        <Link
          className="back-link"
          to={internal ? "/oportunidades-internas" : "/carreiras"}
        >
          ← Todas as oportunidades
        </Link>
        <div className="job-detail-heading">
          <div>
            <p className="eyebrow">{str(job.code)}</p>
            <h1>{str(job.title)}</h1>
            <p className="job-meta">
              <span>
                <MapPin size={17} />
                {str(job.city)} · {str(job.state)}
              </span>
              <span><Building2 size={16} />{label(str(job.modality))}</span>
              <span><Clock3 size={16} />{label(str(job.contract_type))}</span>
            </p>
          </div>
          <div className="job-application-actions">
          <button
            className="button"
            disabled={session.isPending}
            onClick={() => {
              const next = new URL(location.href);
              next.searchParams.set("candidatar", "1");
              const returnTo = next.pathname + next.search + next.hash;
              sessionStorage.setItem("tgpm-selected-vacancy", returnTo);
              if (session.data?.user.kind === "CANDIDATO") navigate("/candidato/perfil?next=" + encodeURIComponent(returnTo));
              else if (session.data) setError(new Error("Entre com uma conta de candidato para se candidatar."));
              else navigate((internal ? "/cadastro-colaborador?next=" : "/cadastro?next=") + encodeURIComponent(returnTo));
            }}
          >
            Candidatar-se
            <ArrowRight size={17} />
          </button>
          </div>
        </div>
        <div className="job-detail-grid">
          <article>
            <section>
              <h2>Sobre a oportunidade</h2>
              <p className="preserve">{str(job.description)}</p>
            </section>
            {[
              ["responsibilities", "Responsabilidades"],
              ["requirements", "Requisitos obrigatórios"],
              ["desirable", "Requisitos desejáveis"],
              ["education", "Formação"],
              ["experience", "Experiência"],
              ["benefits", "Benefícios"],
              ["accessibility", "Acessibilidade"],
            ].map(([key, title]) =>
              details[key] ? (
                <section key={key}>
                  <h2>{title}</h2>
                  <p className="preserve">{str(details[key])}</p>
                </section>
              ) : null,
            )}
          </article>
          <aside className="job-summary">
            <h3>Informações da vaga</h3>
            <dl>
              <dt>Posições</dt>
              <dd>{str(job.quantity)}</dd>
              <dt>Jornada</dt>
              <dd>{str(details.workload) || "Conforme descrição"}</dd>
              <dt>Inscrições até</dt>
              <dd>{new Date(str(job.deadline)).toLocaleDateString("pt-BR")}</dd>
            </dl>
            <h3>Etapas previstas</h3>
            <ol className="steps">
              {rows(job.stages).filter((stage) => !["OFFER", "HIRED"].includes(str(stage.kind).toUpperCase()) && !["proposta", "contratado"].includes(str(stage.name).trim().toLowerCase())).map((s, i) => (
                <li key={i}>{str(s.name)}</li>
              ))}
            </ol>
            <button
              className="button secondary full"
              onClick={async () => {
                try {
                  await navigator.clipboard.writeText(location.href);
                  setConfirmation("Link da vaga copiado.");
                  setError(undefined);
                } catch (e) {
                  setError(e);
                }
              }}
            >
              <Share2 size={16} />
              Copiar link da vaga
            </button>
          </aside>
        </div>
        <ErrorBox error={error} />
        {confirmation && (
          <p className="alert success" role="status">
            {confirmation}
          </p>
        )}
      </main>
      <Modal
        open={open}
        onOpenChange={(value) => {
          setOpen(value);
        }}
        title={"Candidatura · " + str(job.title)}
      >
        <JobEnrollment job={job} invitationToken={invitation ? inviteToken : undefined} />
      </Modal>
    </>
  );
}
export function PublicPrivacy() {
  const query = useQuery({
    queryKey: ["privacy-public"],
    queryFn: () => api<Collection>("/public/privacy"),
  });
  return (
    <>
      <PublicHeader />
      <main className="narrow-page">
        <h1>Privacidade e termos</h1>
        <ConsentTerm />
        <ErrorBox error={query.error} />
        {query.data?.items.map((row) => (
          <article key={row.id}>
            <h2>
              {str(row.name)} · versão {row.version}
            </h2>
            <p className="preserve">{str(obj(row.data).text)}</p>
            <p>Finalidade: {str(obj(row.data).purpose)}</p>
            <p>Contato: {str(obj(row.data).contact)}</p>
          </article>
        ))}
        {!query.isPending && !query.data?.items.length && (
          <Empty title="Nenhum aviso publicado">
            O RH publicará aqui os termos de tratamento de dados antes da
            abertura das candidaturas.
          </Empty>
        )}
      </main>
    </>
  );
}
import { ConsentTerm } from "../components/ConsentTerm";
